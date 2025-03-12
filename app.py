import os
from flask import Flask, render_template
from flask_pymongo import PyMongo


if os.path.exists("env.py"):
    import env


# Initialize the Flask app
app = Flask(__name__)
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)

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