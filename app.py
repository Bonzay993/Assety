import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy



app = Flask(__name__)

db = SQLAlchemy()


if os.path.exists("env.py"):
    import env

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
    app.run(host=os.environ.get("IP"),
        port=int(os.environ.get("PORT")),
        debug=True)
