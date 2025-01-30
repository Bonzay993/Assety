import os
from flask import Flask, render_template


app = Flask(__name__)


if os.path.exists("env.py"):
    import env

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/sign-up')
def sign_up():
    return render_template('sign-up.html')


if __name__ == "__main__":
    app.run(host=os.environ.get("IP"),
        port=int(os.environ.get("PORT")),
        debug=True)
