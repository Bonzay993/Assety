import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_pymongo import PyMongo
from pymongo import MongoClient
from datetime import datetime, timedelta
from flask import render_template, session
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId 
from send_emails import EmailService
import gridfs

if os.path.exists("env.py"):
    import env

# Initialize the Flask app
app = Flask(__name__)
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")
app.config['SESSION_COOKIE_NAME'] = 'session'  # Customize the cookie name (optional)
app.config['SESSION_PERMANENT'] = False  # Session will not last beyond the browser session
app.config['SESSION_TYPE'] = 'filesystem'  # Store session in the filesystem, can also be 'redis' or 'mongodb

app.config['SECRET_KEY'] = 'top-secret!'
app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'
app.config['MAIL_PASSWORD'] = os.environ.get('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
app.config['SENDGRID_API_KEY'] = os.environ.get('SENDGRID_API_KEY') 

email_service = EmailService(app)
mongo = PyMongo(app)

# Initialize GridFS
fs = gridfs.GridFS(mongo.cx[app.config["MONGO_DBNAME"]])




@app.route('/')
def index():
    return render_template('index.html')



@app.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    try:
        # Directly connect using MongoClient
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        users_collection = db['users']  # Access 'users' collection directly
        # Check if connection was successful by listing collection names
        collections = db.list_collection_names()
        print(f"Collections available: {collections}")

        if request.method == 'POST':
            first_name = request.form.get('first-name')
            last_name = request.form.get('last-name')
            company = request.form.get('company')
            email = request.form.get('email')
            password = request.form.get('password')

            # Check if the email or company already exists in the database
            existing_user = users_collection.find_one({'email': email})
            # Check if the company name already exists in the database
            existing_company = db.list_collection_names()  # List of all collections in the DB
            if company in existing_company:
                flash("Company name in use. Please ask your admin to provide credentials or contact support.", "signup-company-error")
                return redirect(url_for('sign_up'))

            if existing_user:
                flash("An account with this email already exists. Please use a different email.", "signup-email-error")
                return redirect(url_for('sign_up'))

            # Hash the password after POST request
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

            # Add user data to the users collection
            user_data = {
                'first_name': first_name,
                'last_name': last_name,
                'company': company,
                'email': email,
                'password': hashed_password
            }

            try:
                # Insert user into the 'users' collection first
                user_insert = users_collection.insert_one(user_data)

                # Create a new collection named after the company (linked to the user)
                company_collection = db[company]  # Use the sanitized company name for collection

                company_data = {
                    'user_id': user_insert.inserted_id,  # Link the company collection to the user ID
                    'company_name': company
                }

                # Insert an initial document into the company's collection (optional)
                company_collection.insert_one(company_data)

                # Successfully created user and company collection
                flash("Account created successfully! Please log in.", "signup-success")
                return redirect(url_for('login'))  # Redirect to login after successful signup

            except Exception as e:
                flash(f"An error occurred: {str(e)}", "error")
                return redirect(url_for('sign_up'))

        return render_template('sign-up.html')

    except Exception as e:
        print(f"Error: {e}")
        flash("MongoDB connection failed. Please try again later.", "error")
        return render_template('sign-up.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    session.permanent = False
   
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        users_collection = db['users']
        user = users_collection.find_one({'email': email})  # Find user by email

        if user and check_password_hash(user['password'], password):
            session['user_logged_in'] = True
            session['user_id'] = str(user['_id'])  # Store user ID in session
            session['first_name'] = user.get('first_name', 'User').capitalize()  # Store first name in session
            session['company'] = user['company']
            print(f"Session after login: {session}")  # Debugging session data
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))  # Redirect to inventory page
        else:
            flash('Invalid credentials. Please try again.', 'login')  # Category 'danger' for login error

    return render_template('login.html')


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    if request.method == 'POST':
        return '', 204  # JS handles message
    return redirect(url_for('login'))




@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
      
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        email = request.form.get("email").lower()
        users_collection = db['users']
        user = users_collection.find_one({'email': email})  # Find user by email
        
        
        if user:
            # Generate a token for password reset
            token = email_service.generate_token(email)
            reset_url = url_for('reset_password', token=token, _external=True)

            # Send the password reset email
            subject = "Assety Password Reset Request"
            html_content = f"<p>Click the following link to reset your password:</p> <a href='{reset_url}'>{reset_url}</a>"
            response = email_service.send_email(email, subject, html_content)

            if response:
                flash("If this email is valid, you will receive a password reset link shortly.", 'reset-password-message')
            else:
                flash("An error occurred while sending the reset email. Please try again later.", 'reset-password-message-error')

        else:
            flash("If this email is valid, you will receive a password reset link shortly.", 'reset-password-message')
        
        # Render the same page to display the flash message
        return render_template("forgot-password.html")

    return render_template("forgot-password.html")



@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = email_service.verify_token(token)
    if not email:
        flash("The password reset link is invalid or has expired.", 'password-update-expired')
        return redirect(url_for('login'))

    if request.method == "POST":
        new_password = request.form.get("password")
        hashed_password = generate_password_hash(new_password)
        
        # Update the password in the database
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        users_collection = db['users']
        user = users_collection.update_one({"email": email}, {"$set": {"password": hashed_password}})
        
        flash("Your password has been updated successfully.", 'password-update-success')
        return redirect(url_for('login'))
    else:
        flash("There was something wrong while updating the password. Please try again later,'password-update-fail")
    
    return render_template("reset-password.html", token=token)



@app.route('/inventory')
def inventory_app():
    # Get the first name and company name from the session
    user_first_name = session.get('first_name', 'User')  # Default to 'User' if no first name is found in session
    company_name = session.get('company', 'No Company')  # Default to 'No Company' if no company is found in session
    
    # Replace underscores with spaces in the company name
    company_name = company_name.replace("_", " ")
    
    # Debugging: print session data and modified company name
    print(f"Session data: {session}")
    print(f"User First Name: {user_first_name}")
    print(f"Modified Company Name: {company_name}")
    
    # Render the template with first name and company name
    return render_template('inventory.html', first_name=user_first_name, company=company_name)


@app.route('/dashboard')
def dashboard():
    # Ensure user is logged in
    company_name = session.get('company', None)
    user_first_name = session.get('first_name', 'User')

    if not company_name:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('login'))

    # Normalize company name
    company_name = company_name.replace('_', ' ')

    # Connect to MongoDB
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]

    # Fetch total assets
    total_assets = company_collection.count_documents({"asset": True})

    # Fetch categories (assuming categories exist in asset records)
    categories = company_collection.distinct("category")

    # Fetch recent assets (last 5 added)
    recent_assets = list(company_collection.find({"asset": True}).sort("_id", -1).limit(5))

    # ✅ Fetch recent activities (filtered by user's company only)
    recent_activities_cursor = db.activities.find(
        {"company": company_name}
    ).sort("timestamp", -1).limit(5)

    # ✅ Format activity data for the template
    formatted_activities = []
    for act in recent_activities_cursor:
        formatted_activities.append({
            "date": act.get("timestamp"),
            "user": act.get("user"),            
            "action": act.get("action"),
            "asset": act.get("asset"),          
            "location": act.get("location", "N/A")
    })


    # Render dashboard template
    return render_template(
        "dashboard.html",
        first_name=user_first_name,
        company=company_name,
        total_assets=total_assets,
        categories=categories,
        recent_assets=recent_assets,
        recent_activities=formatted_activities  # Use formatted activities
    )


def log_activity(action, asset_id, asset_tag, location=None):
    """Logs the activity to the 'activities' collection"""
    user_name = session.get('first_name', 'Unknown User')
    company_name = session.get('company')
    timestamp = datetime.now()

    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    activities_collection = db['activities']

    activity_data = {
        'user': user_name,
        'action': action,
        'asset_id': asset_id,
        'asset_tag': asset_tag,
        'timestamp': timestamp,
        'location': location or 'N/A',
        'company': company_name
    }

    print(f"LOGGED ACTIVITY: {activity_data}")  # Optional debugging log
    activities_collection.insert_one(activity_data)


@app.route('/test-mongo')
def test_mongo():
    try:
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        collections = db.list_collection_names()
        return f"Connected to MongoDB! Collections: {collections}", 200
    except Exception as e:
        return f"Error connecting to MongoDB: {str(e)}", 500


@app.route("/assets")
def assets():
    # Debugging: Check the session data
    print(f"Session at assets page: {session}")

    # Get the first name from the session, if available
    user_first_name = session.get('first_name', 'User')
    company_name = session.get('company', 'No Company')

    company_name = company_name.replace("_", " ")

    # Fetch assets from the database as before
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    
      # Access the company's asset collection
    company_collection = db[company_name]

    # Fetch only assets where "asset" is True
    all_assets = list(company_collection.find({"asset": True}))
    
    # Pass the assets and first name to the template
    return render_template("assets.html", assets=all_assets, first_name=user_first_name, company=company_name)

@app.route("/new-asset")
def new_asset():
     user_first_name = session.get('first_name', 'User') 
     company_name = session.get('company', None)
     company_name = company_name.replace("_", " ")

     client = MongoClient(app.config["MONGO_URI"])
     db = client[app.config["MONGO_DBNAME"]]

     company_collection = db[company_name]
     
     locations = list(company_collection.find({"location": True}))
     categories = list(company_collection.find({"category": True}))
     
     return render_template("new-asset.html",first_name=user_first_name, company=company_name, locations=locations, categories=categories )


@app.route('/save_asset', methods=['POST'])
def save_asset():
    company_name = session.get('company')
    if not company_name:
        flash("No company found in session. Please log in again.", "error")
        return redirect(url_for('login'))

    company_name = company_name.replace('_', ' ')
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]
    fs = gridfs.GridFS(db)

    asset_id = request.form.get('asset_id')
    asset_tag = request.form['asset-tag']
    serial = request.form['serial']
    model = request.form['model']
    notes = request.form['notes']
    warranty = request.form['warranty']
    order_number = request.form['order-number']
    purchase_cost = request.form['purchase-cost']
    purchase_date = request.form['purchase-date']
    location = request.form['location']
    category = request.form['category']

    image_file = request.files.get('image')
    image_id = None

    if image_file and image_file.filename != "":
        try:
            filename = secure_filename(image_file.filename)
            image_id = fs.put(
                image_file,
                filename=filename,
                content_type=image_file.content_type,
                company=company_name,
                uploaded_by=session.get('first_name'),
                asset_tag=asset_tag,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            flash(f"Image upload failed: {str(e)}", "error")
            return redirect(url_for('dashboard'))
    elif asset_id:
        # 🛠 Preserve current image_id if no new image uploaded
        existing_asset = company_collection.find_one({"_id": ObjectId(asset_id)})
        if existing_asset and 'image_id' in existing_asset:
            image_id = existing_asset['image_id']

    asset_data = {
        'asset': True,
        'asset_tag': asset_tag,
        'serial': serial,
        'model': model,
        'notes': notes,
        'warranty': warranty,
        'order_number': order_number,
        'purchase_cost': purchase_cost,
        'purchase_date': purchase_date,
        'location': location,
        'image_id': image_id,
        'category': category,
    }

    try:
        if asset_id:
            company_collection.update_one(
                {"_id": ObjectId(asset_id)},
                {"$set": asset_data}
            )
            action = 'Update'
            flash("Asset updated successfully!", "success")
        else:
            company_collection.insert_one(asset_data)
            action = 'Create'
            flash("New asset created!", "success")

        db.activities.insert_one({
            'timestamp': datetime.now(),
            'user': session.get('first_name'),
            'action': action,
            'asset': asset_tag,
            'location': location,
            'company': company_name,
            'category': category
        })

        return redirect(url_for('assets'))

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for('dashboard'))



@app.route('/image/<image_id>')
def get_image(image_id):
    company = session.get('company')
    if not company:
        return "Unauthorized", 403

    try:
        image_file = fs.get(ObjectId(image_id))
        # Check if image belongs to the correct company
        if image_file.company != company:
            return "Forbidden", 403

        return send_file(image_file, mimetype=image_file.content_type)

    except Exception as e:
        return f"Image not found: {str(e)}", 404



@app.route('/asset-properties')
def asset_properties():
    asset_id = request.args.get('asset_id')  # Get asset ID from URL
    user_first_name = session.get('first_name', 'User') 
    company_name = session.get('company', None)
    company_name = company_name.replace("_", " ")

    image_file = request.files.get('image')
    image_id = None

    if image_file and image_file.filename != "":
        try:
            filename = secure_filename(image_file.filename)
            image_id = fs.put(
                image_file,
                filename=filename,
                content_type=image_file.content_type,
                company=company_name,
                uploaded_by=session.get('first_name'),
                asset_tag=asset_tag,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            flash(f"Image upload failed: {str(e)}", "error")
            return redirect(url_for('dashboard'))
    
    if asset_id:
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[session.get('company', 'default_company')]
        locations = list(company_collection.find({"location": True}))
        categories = list(company_collection.find({"category": True}))

        asset = company_collection.find_one({"_id": ObjectId(asset_id)})  # Fetch asset

        if asset:
            return render_template("asset-properties.html", asset=asset,first_name=user_first_name, locations=locations, company=company_name ,categories=categories)  

    return render_template("asset-properties.html", asset=None, )  # If no asset ID, load empty form


@app.route('/delete_asset/<asset_id>', methods=['POST'])
def delete_asset(asset_id):
    try:
        # Get the company name from session
        company_name = session.get('company', None)
        if not company_name:
            flash("No company found in session. Please log in again.", "error")
            return redirect(url_for('login'))

        # Replace underscores with spaces in company name (if needed)
        company_name = company_name.replace("_", " ")

        # Connect to MongoDB
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[company_name]

        asset = company_collection.find_one({"_id": ObjectId(asset_id)})

        if not asset:
            flash("Asset not found!", "danger")
            return redirect(url_for('assets'))

        # Attempt to find and delete the asset
        result = company_collection.delete_one({"_id": ObjectId(asset_id)})

        if result.deleted_count > 0:
            # Log the delete activity
            activity_data = {
                'timestamp': datetime.now(),
                'user': session.get('first_name'),
                'action': 'Delete',  # Correct action
                'asset': asset.get('asset_tag'),  # Use asset_tag from the asset document
                'location': asset.get('location', 'N/A'),  # Use location from the asset document
                'company': company_name
            }
            db.activities.insert_one(activity_data)

            flash("Asset deleted successfully", "success")
        else:
            flash("Asset not found!", "danger")

    except Exception as e:
        flash(f"Error deleting asset: {str(e)}", "danger")

    return redirect(url_for('assets'))


@app.route('/asset/<asset_id>')
def view_asset(asset_id):
    
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    user_first_name = session.get('first_name', 'User') 
    company_name = session.get('company', None)
    company_name = company_name.replace("_", " ")
    company_collection = db[company_name]

    # Fetch asset details from the database using the provided asset_id
    asset = company_collection.find_one({"_id": ObjectId(asset_id)})

    # Pair labels and values
    labels = [
        'Asset Name', 'Model', 'Serial', 'Location', 'Category', 'Purchase Date', 'Purchase Cost'
    ]
    values = [
        asset.get('asset_tag'), asset.get('model'), asset.get('serial'),
        asset.get('location'), asset.get('category'), asset.get('purchase_date'),
        asset.get('purchase_cost')
    ]
    labels_values = list(zip(labels, values))

    return render_template('view-asset.html', asset=asset, company=company_name, labels_values=labels_values, first_name=user_first_name)



        

@app.route('/locations')
def locations():
    # Debugging: Check the session data
    print(f"Session at assets page: {session}")

    # Get the first name from the session, if available
    user_first_name = session.get('first_name', 'User')
    company_name = session.get('company', 'No Company')

    company_name = company_name.replace("_", " ")

    # Fetch assets from the database as before
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    
      # Access the company's asset collection
    company_collection = db[company_name]

    # Fetch only assets where "asset" is True
    all_locations = list(company_collection.find({"location": True}))
    
    # Pass the assets and first name to the template
    return render_template("locations.html", locations=all_locations, first_name=user_first_name, company=company_name)


@app.route('/new-location')
def new_location():
    company_name = session.get('company', None)
    user_first_name = session.get('first_name', 'User')
    return render_template("new-location.html",first_name=user_first_name, company=company_name )



@app.route('/save-location', methods=['POST'])
def save_location():
    company_name = session.get('company', None)  # Ensure correct indentation

    if not company_name:
        flash("No company found in session. Please log in again.", "error")
        return redirect(url_for('login'))

    # Replace underscores with spaces in the company name if needed
    company_name = company_name.replace('_', ' ')

    # Access MongoDB
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]

    # Ensure the collection name corresponds to the company name
    company_collection = db[company_name]  # Using company name as collection name
    

    # Get form data from the POST request
    location_id = request.form.get('location_id')
    location_tag = request.form['location-tag']
    phone = request.form['phone']  # Changed from 'phone' to 'serial' (match your form)
    address = request.form['address']  # Changed from 'address' to 'model' (match your form)
    city = request.form['city']
    state = request.form['state']
    post_code = request.form['post-code']

    # Create the location data dictionary
    location_data = {
        'location':True,
        'location_tag': location_tag,
        'phone': phone,
        'address': address,
        'city': city,
        'state': state,
        'post_code': post_code
    }

    try:
        if location_id:
            # Insert the data into the company-specific collection
            company_collection.update_one(
                {"_id": ObjectId(location_id)},
                {"$set": location_data}
            )

            activity_data={
                'date':datetime.datetime.now(),
                'user': session['first_name'],
                'action': 'Update',
                'location': location_tag
            }
            db.activities.insert_one(activity_data)
            flash("Location updated succesfully!","success")
        else:
            company_collection.insert_one(location_data)
            activity_data = {
                'date': datetime.datetime.now(),
                'user': session['first_name'],
                'action': 'Create',  # Log the creation action
                'location': location_tag
            }
            db.activities.insert_one(activity_data)
            flash("New location created!", "success")
            

        
        return redirect(url_for('locations'))  # Redirect to inventory page

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for('dashboard'))  # Redirect on error

@app.route('/location-properties')
def location_properties():
    location_id = request.args.get('location_id')  # Get asset ID from URL
    
    if location_id:
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[session.get('company', 'default_company')]

        location = company_collection.find_one({"_id": ObjectId(location_id)})  # Fetch asset

        if location:
            return render_template("location-properties.html", location=location)  

    return render_template("location-properties.html", asset=None)  # If no asset ID, load empty form


@app.route('/delete_location/<location_id>', methods=['POST'])
def delete_location(location_id):
    try:
        # Get the company name from session
        company_name = session.get('company', None)
        if not company_name:
            flash("No company found in session. Please log in again.", "error")
            return redirect(url_for('login'))

        # Replace underscores with spaces in company name (if needed)
        company_name = company_name.replace("_", " ")

        # Connect to MongoDB
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[company_name]

        location = company_collection.find_one({"_id": ObjectId(location_id)})

        if not location:
            flash("Location not found!", "danger")
            return redirect(url_for('locations'))

        # Attempt to find and delete the asset
        result = company_collection.delete_one({"_id": ObjectId(location_id)})

        if result.deleted_count > 0:
            # Log the delete activity
            activity_data = {
                'date': datetime.datetime.now(),
                'user': session['first_name'],
                'action': 'Delete',
                'location': location.get('location_tag', 'Unknown location')  # Use asset_tag or a fallback
            }
            db.activities.insert_one(activity_data)

            flash("Location deleted successfully", "success")
        else:
            flash("Location not found!", "danger")

    except Exception as e:
        flash(f"Error deleting location: {str(e)}", "danger")

    return redirect(url_for('locations'))


@app.route('/categories')
def categories():
    print(f"Session at categories page: {session}")

    user_first_name = session.get('first_name', 'User')
    company_name = session.get('company', 'No Company').replace("_", " ")

    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]  

    # Fetch all categories for this company
    all_categories = list(company_collection.find({"category": True}))

    # Count items per category by matching category name
    for category in all_categories:
        category_name = category["name"]
        item_count = company_collection.count_documents({
            "$and": [
                {"category": category_name},
                {"category": {"$type": "string"}}
            ]
        })
        category["quantity"] = item_count

    return render_template(
        "categories.html",
        categories=all_categories,
        first_name=user_first_name,
        company=company_name
    )

@app.route('/new-category')
def new_category():
    company_name = session.get('company', None)
    user_first_name = session.get('first_name', 'User')

    if request.args.get("modal") == "true":
        # Render only the form part for use in a modal
        return render_template("category_modal_form.html", first_name=user_first_name, company=company_name)
    
    # Otherwise, render the full page with layout
    return render_template("new-category.html", first_name=user_first_name, company=company_name)



from flask import request, redirect, url_for, session, render_template, flash
from werkzeug.utils import secure_filename
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
import gridfs

@app.route('/save_category', methods=['POST'])
def save_category():
    company_name = session.get('company')
    if not company_name:
        flash("No company found in session. Please log in again.", "error")
        return redirect(url_for('login'))

    is_modal = request.args.get('modal') == 'true'
    company_name = company_name.replace('_', ' ')
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]
    fs = gridfs.GridFS(db)

    category_id = request.form.get('category_id')
    category_name = request.form['category-name']
    category_type = request.form['category-type']

    # Prevent duplicate category names (case-insensitive)
    query = {"category": True, "name": {"$regex": f"^{category_name}$", "$options": "i"}}
    if category_id:
        query["_id"] = {"$ne": ObjectId(category_id)}

    existing = company_collection.find_one(query)
    if existing:
        if is_modal:
            return '''
                <script>
                    alert("A category with this name already exists.");
                    window.history.back();
                </script>
            '''
        else:
            flash("A category with this name already exists.", "category-error")
            if category_id:
                return redirect(url_for('category_properties', category_id=category_id))
            else:
                return render_template(
                    "new-category.html",
                    category={"name": category_name, "type": category_type},
                    first_name=session.get('first_name', 'User'),
                    company=company_name
                )

    # Image upload
    image_file = request.files.get('image')
    image_id = None

    if image_file and image_file.filename != "":
        try:
            filename = secure_filename(image_file.filename)
            image_id = fs.put(
                image_file,
                filename=filename,
                content_type=image_file.content_type,
                company=company_name,
                uploaded_by=session.get('first_name'),
                category_name=category_name,
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            if is_modal:
                return f"<script>alert('Image upload failed: {str(e)}');</script>"
            flash(f"Image upload failed: {str(e)}", "error")
            return redirect(url_for('dashboard'))
    elif category_id:
        existing_category = company_collection.find_one({"_id": ObjectId(category_id)})
        if existing_category and 'image_id' in existing_category:
            image_id = existing_category['image_id']

    category_data = {
        'category': True,
        'name': category_name,
        'type': category_type,
        'image_id': image_id
    }

    try:
        if category_id:
            company_collection.update_one(
                {"_id": ObjectId(category_id)},
                {"$set": category_data}
            )
            action = 'Update Category'
        else:
            company_collection.insert_one(category_data)
            action = 'Create Category'

        db.activities.insert_one({
            'timestamp': datetime.now(),
            'user': session.get('first_name'),
            'action': action,
            'category': category_name,
            'company': company_name
        })

        if is_modal:
            return '''
                <script>
                    alert("Category saved successfully!");
                    window.parent.location.reload();
                </script>
            '''
        else:
            flash("Category saved successfully!", "category-success")
            return redirect(url_for('categories'))

    except Exception as e:
        if is_modal:
            return f"<script>alert('An error occurred: {str(e)}');</script>"
        flash(f"An error occurred while saving category: {str(e)}", "category-error")
        return redirect(url_for('dashboard'))



@app.route('/category-properties')
def category_properties():
    category_id = request.args.get('category_id')  # Get category ID from URL
    
    if category_id:
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[session.get('company', 'default_company')]

        category = company_collection.find_one({
            "_id": ObjectId(category_id),
            "category": True
        })  # Ensure it's actually a category

        if category:
            return render_template("category-properties.html", category=category)

    # If no valid ID or not found, load empty template
    return render_template("category-properties.html", category=None)


@app.route('/delete_category/<category_id>', methods=['POST'])
def delete_category(category_id):
    try:
        # Get the company name from session
        company_name = session.get('company', None)
        if not company_name:
            flash("No company found in session. Please log in again.", "error")
            return redirect(url_for('login'))

        company_name = company_name.replace("_", " ")

        # Connect to MongoDB
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[company_name]

        # Find the category
        category = company_collection.find_one({"_id": ObjectId(category_id), "category": True})

        if not category:
            flash("Category not found!", "danger")
            return redirect(url_for('categories'))

        # Delete the category
        result = company_collection.delete_one({"_id": ObjectId(category_id)})

        if result.deleted_count > 0:
            # Log the delete activity
            activity_data = {
                'date': datetime.datetime.now(),
                'user': session['first_name'],
                'action': 'Delete Category',
                'category': category.get('name', 'Unknown category'),
                'company': company_name
            }
            db.activities.insert_one(activity_data)

            flash("Category deleted successfully", "success")
        else:
            flash("Failed to delete category.", "danger")

    except Exception as e:
        flash(f"Error deleting category: {str(e)}", "danger")

    return redirect(url_for('categories'))


if __name__ == "__main__":
    app.run(host=os.environ.get("IP", "0.0.0.0"),
            port=int(os.environ.get("PORT", 5000)),
            debug=True)