import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_pymongo import PyMongo
from pymongo import MongoClient
from flask import render_template, session
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash

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
            return redirect(url_for('inventory_app'))  # Redirect to inventory page
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
    
    laptops_collection = db['laptops']
    computers_collection = db['computers']
    
    all_laptops = list(laptops_collection.find({}))
    all_computers = list(computers_collection.find({}))

    all_assets = all_laptops + all_computers
    
    # Pass the assets and first name to the template
    return render_template("assets.html", assets=all_assets, first_name=user_first_name, company=company_name)

@app.route("/new-asset")
def new_asset():
     company_name = session.get('company', None)
     user_first_name = session.get('first_name', 'User') 
     return render_template("new-asset.html",first_name=user_first_name, company=company_name )



@app.route('/save_asset', methods=['POST'])
def save_asset():
    # Get the company name from the session (assuming it's stored as 'company')
    company_name = session.get('company', None)
     # Default to 'User' if no first name is found in session
    

    # Check if the company is in the session, if not, redirect or show an error
    if not company_name:
        flash("No company found in session. Please log in again.", "error")
        return redirect(url_for('login'))

    # Replace underscores with spaces in the company name if needed
    company_name = company_name.replace('_', ' ')

    # Access MongoDB
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DBNAME"]]

    # Ensure the collection name corresponds to the company name (create dynamically)
    company_collection = db[company_name]  # Using company name as collection name

    # Get form data from the POST request
    asset_tag = request.form['asset-tag']
    serial = request.form['serial']
    model = request.form['model']
    notes = request.form['notes']
    warranty = request.form['warranty']
    order_number = request.form['order-number']
    purchase_cost = request.form['purchase-cost']

    # Create the asset data dictionary
    asset_data = {
        'asset_tag': asset_tag,
        'serial': serial,
        'model': model,
        'notes': notes,
        'warranty': warranty,
        'order_number': order_number,
        'purchase_cost': purchase_cost,
    }

    try:
        # Insert the asset data into the company-specific collection
        company_collection.insert_one(asset_data)

        flash("Asset saved successfully!", "success")
        return redirect(url_for('inventory_app'))  # Redirect to the inventory page

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for('inventory_app'))  # Redirect to the inventory page



if __name__ == "__main__":
    app.run(host=os.environ.get("IP", "0.0.0.0"),
            port=int(os.environ.get("PORT", 5000)),
            debug=True)