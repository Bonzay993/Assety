import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_pymongo import PyMongo
from pymongo import MongoClient
from flask import render_template, session
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from bson.objectid import ObjectId 
import datetime
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

            # Check if the email already exists in the database
            existing_user = users_collection.find_one({'email': email})

            if existing_user:
                flash("An account with this email already exists. Please use a different email.", "error")
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
                flash("Account created successfully! Please log in.", "success")
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
            session['user_id'] = str(user['_id'])  # Store user ID in session
            session['first_name'] = user.get('first_name', 'User').capitalize()  # Store first name in session
            session['company'] = user['company']
            print(f"Session after login: {session}")  # Debugging session data
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))  # Redirect to inventory page
        else:
            flash('Invalid credentials. Please try again.', 'danger')  # Category 'danger' for login error

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()  # Clears all session data
    flash('You have been logged out!', 'info')
    return redirect(url_for('login'))  # Redirects to login page


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

    # Fetch recent activities (last 5 activities)
    recent_activities = list(db.activities.find().sort("date", -1).limit(5))

    return render_template(
        "dashboard.html",
        first_name=user_first_name,
        company=company_name,
        total_assets=total_assets,
        categories=categories,
        recent_assets=recent_assets,
        recent_activities=recent_activities  # Pass activities to the template
    )


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
     
     return render_template("new-asset.html",first_name=user_first_name, company=company_name, locations=locations )


@app.route('/save_asset', methods=['POST'])
def save_asset():
    company_name = session.get('company', None)
    if not company_name:
        flash("No company found in session. Please log in again.", "error")
        return redirect(url_for('login'))

    company_name = company_name.replace('_', ' ')
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]

    asset_id = request.form.get('asset_id')  # Get the asset ID if editing
    asset_tag = request.form['asset-tag']
    serial = request.form['serial']
    model = request.form['model']
    notes = request.form['notes']
    warranty = request.form['warranty']
    order_number = request.form['order-number']
    purchase_cost = request.form['purchase-cost']
    purchase_date = request.form['purchase-date']
    location = request.form['location']  # Capture selected location

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
        'location': location
    }

    try:
        if asset_id:  # If asset exists, UPDATE instead of inserting a new one
            company_collection.update_one(
                {"_id": ObjectId(asset_id)},
                {"$set": asset_data}
            )
            # Log the update activity
            activity_data = {
                'date': datetime.datetime.now(),
                'user': session['first_name'],
                'action': 'Update',
                'asset': asset_tag
            }
            db.activities.insert_one(activity_data)

            flash("Asset updated successfully!", "success")
        else:
            company_collection.insert_one(asset_data)
            activity_data = {
                'date': datetime.datetime.now(),
                'user': session['first_name'],
                'action': 'Create',  # Log the creation action
                'asset': asset_tag
            }
            db.activities.insert_one(activity_data)
            flash("New asset created!", "success")

        return redirect(url_for('assets'))  

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for('dashboard'))

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for('dashboard'))



@app.route('/asset-properties')
def asset_properties():
    asset_id = request.args.get('asset_id')  # Get asset ID from URL
    
    if asset_id:
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[session.get('company', 'default_company')]

        asset = company_collection.find_one({"_id": ObjectId(asset_id)})  # Fetch asset

        if asset:
            return render_template("asset-properties.html", asset=asset)  

    return render_template("asset-properties.html", asset=None)  # If no asset ID, load empty form


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
                'date': datetime.datetime.now(),
                'user': session['first_name'],
                'action': 'Delete',
                'asset': asset.get('asset_tag', 'Unknown Asset')  # Use asset_tag or a fallback
            }
            db.activities.insert_one(activity_data)

            flash("Asset deleted successfully", "success")
        else:
            flash("Asset not found!", "danger")

    except Exception as e:
        flash(f"Error deleting asset: {str(e)}", "danger")

    return redirect(url_for('assets'))



def log_activity(action, asset_id, asset_tag):
    """Logs the activity to the 'activities' collection"""
    user_id = session.get('user_id')
    company_name = session.get('company')
    timestamp = datetime.datetime.now()

    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]
    activities_collection = db['activities']  # You should create this collection in MongoDB

    activity_data = {
        'user_id': user_id,
        'action': action,
        'asset_id': asset_id,
        'asset_tag': asset_tag,
        'timestamp': timestamp,
        'company': company_name
    }

    activities_collection.insert_one(activity_data)
        

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


@app.route("/categories")
def categories():
    return render_template("categories.html")


if __name__ == "__main__":
    app.run(host=os.environ.get("IP", "0.0.0.0"),
            port=int(os.environ.get("PORT", 5000)),
            debug=True)