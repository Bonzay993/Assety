import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

# Import env.py to load environment variables
import env

db = SQLAlchemy()

# Initialize the Flask app
app = Flask(__name__)

# Use the DATABASE_URL from environment variables
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Optional, disable modification tracking

# Initialize the database with the app
db.init_app(app)

# Define routes inside the function
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sign-up')
def sign_up():
    return render_template('sign-up.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/inventory')
def inventory_app():
    return render_template('inventory.html')

if __name__ == "__main__":
    app.run(host=os.environ.get("IP", "0.0.0.0"),
            port=int(os.environ.get("PORT", 5000)),
            debug=True)