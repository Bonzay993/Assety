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

            # Try to insert the user and handle possible exceptions
            try:
                users_collection.insert_one(user_data)
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
            flash('Login successful!', 'success')
            return redirect(url_for('inventory_app'))  # Redirect to inventory page
        else:
            flash('Invalid credentials. Please try again.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()  # Clears all session data
    flash('You are now logged out!', 'success')
    return redirect(url_for('login'))  # Redirects to login page


@app.route('/inventory')
def inventory_app():
    user_first_name = session.get('first_name', 'User')  # Retrieve first name from session or default to 'User'
    return render_template('inventory.html', first_name=user_first_name)

@app.route('/test-mongo')
def test_mongo():
    try:
        client = MongoClient(app.config["MONGO_URI"])
        db = client[app.config["MONGO_DBNAME"]]
        collections = db.list_collection_names()
        return f"Connected to MongoDB! Collections: {collections}", 200
    except Exception as e:
        return f"Error connecting to MongoDB: {str(e)}", 500

if __name__ == "__main__":
    app.run(host=os.environ.get("IP", "0.0.0.0"),
            port=int(os.environ.get("PORT", 5000)),
            debug=True)