import os
import csv
import io
import math
import re
import secrets
import atexit
from decimal import Decimal, InvalidOperation
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, jsonify, abort, g
from flask_pymongo import PyMongo
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from markupsafe import escape
from bson.objectid import ObjectId 
from bson.errors import InvalidId
from send_emails import EmailService
from fpdf import FPDF
from translations import TRANSLATIONS
import gridfs

if os.path.exists("env.py"):
    import env

# Initialize the Flask app
app = Flask(__name__)
app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
if os.environ.get('DYNO') and not os.environ.get('SECRET_KEY'):
    raise ValueError('Set SECRET_KEY in Heroku Config Vars before starting Assety.')
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SESSION_COOKIE_NAME'] = 'session'  # Customize the cookie name (optional)
app.config['SESSION_PERMANENT'] = False  # Session will not last beyond the browser session
app.config['SESSION_TYPE'] = 'filesystem'  # Store session in the filesystem, can also be 'redis' or 'mongodb

app.config['MAIL_SERVER'] = 'smtp.sendgrid.net'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'apikey'
app.config['MAIL_PASSWORD'] = os.environ.get('SENDGRID_API_KEY')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
app.config['SENDGRID_API_KEY'] = os.environ.get('SENDGRID_API_KEY') 

email_service = EmailService(app)
mongo = PyMongo(app)
atexit.register(mongo.cx.close)
app.config['MONGO_DBNAME'] = app.config['MONGO_DBNAME'] or (mongo.db.name if mongo.db is not None else None)
if not app.config['MONGO_DBNAME']:
    raise ValueError('Set MONGO_DBNAME or include a database name in MONGO_URI.')

# Initialize GridFS
fs = gridfs.GridFS(mongo.cx[app.config["MONGO_DBNAME"]])


# Currency symbols mapping
CURRENCY_SYMBOLS = {
    'GBP': '£',
    'USD': '$',
    'EUR': '€'
}


def email_query(email):
    """Match legacy mixed-case email addresses without interpreting regex syntax."""
    return {'email': {'$regex': '^' + re.escape(email) + '$', '$options': 'i'}}


def valid_email(email):
    return isinstance(email, str) and bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email))


def valid_password(password, confirmation):
    return (isinstance(password, str) and len(password) >= 6
            and bool(re.search(r'[A-Z]', password)) and password == confirmation)


def pdf_text(value):
    # FPDF's core fonts use Windows-1252; its output method expects Latin-1 bytes.
    return str(value).encode('cp1252', errors='replace').decode('latin1')


def activity_date(activity):
    return activity.get('timestamp') or activity.get('date')


def activity_label(activity):
    return activity.get('asset') or activity.get('asset_tag') or activity.get('category') or ''


def delete_unused_image(collection, image_id):
    if image_id and not collection.find_one({'image_id': image_id}):
        fs.delete(image_id)


def activity_date_filter(company):
    bounds = {}
    for argument, operator in [('start_date', '$gte'), ('end_date', '$lt')]:
        value = request.args.get(argument)
        if value:
            try:
                parsed = datetime.strptime(value, '%Y-%m-%d')
                bounds[operator] = parsed + timedelta(days=1) if argument == 'end_date' else parsed
            except ValueError:
                pass
    query = {'company': company}
    if bounds:
        query['$or'] = [
            {'timestamp': bounds},
            {'timestamp': {'$exists': False}, 'date': bounds},
        ]
    return query


def activity_cursor(db, query, skip=0, limit=None):
    pipeline = [
        {'$match': query},
        {'$addFields': {'event_date': {'$ifNull': ['$timestamp', '$date']}}},
        {'$sort': {'event_date': -1, '_id': -1}},
        {'$skip': skip},
    ]
    if limit is not None:
        pipeline.append({'$limit': limit})
    return db.activities.aggregate(pipeline)


@app.before_request
def require_account():
    public = {'index', 'login', 'sign_up', 'forgot_password', 'reset_password',
              'logout', 'static', 'test_mongo'}
    if request.endpoint is None or request.endpoint in public:
        return
    user_id = session.get('user_id')
    try:
        user = mongo.cx[app.config['MONGO_DBNAME']].users.find_one({'_id': ObjectId(user_id)}) if user_id else None
    except (InvalidId, TypeError):
        user = None
    if not user or not user.get('company'):
        session.clear()
        if request.endpoint in {'save_settings', 'update_profile', 'search_assets'}:
            return jsonify(status='unauthorized'), 401
        if request.endpoint == 'get_image':
            return 'Unauthorized', 403
        return redirect(url_for('login'))
    g.current_user = user
    # The user's persisted company is the collection key, never a display name.
    session['company'] = user['company']

    resources = {
        'view_asset': ('asset_id', 'asset', 'path'),
        'delete_asset': ('asset_id', 'asset', 'path'),
        'asset_properties': ('asset_id', 'asset', 'query'),
        'save_asset': ('asset_id', 'asset', 'form'),
        'delete_category': ('category_id', 'category', 'path'),
        'category_properties': ('category_id', 'category', 'query'),
        'save_category': ('category_id', 'category', 'form'),
        'delete_location': ('location_id', 'location', 'path'),
        'location_properties': ('location_id', 'location', 'query'),
        'save_location': ('location_id', 'location', 'form'),
    }
    resource = resources.get(request.endpoint)
    if resource:
        field, flag, source = resource
        values = request.view_args if source == 'path' else request.args if source == 'query' else request.form
        value = values.get(field)
        if not value and source == 'form':
            return
        try:
            object_id = ObjectId(value) if value else None
        except (InvalidId, TypeError):
            abort(404)
        collection = mongo.cx[app.config['MONGO_DBNAME']][user['company']]
        g.item = collection.find_one({'_id': object_id, flag: True}) if object_id else None
        if g.item is None:
            abort(404)




@app.context_processor
def inject_translator():
    """Provide a simple translation function to templates."""
    language = session.get('language', 'en')

    def trans(key):
        return TRANSLATIONS.get(language, TRANSLATIONS['en']).get(key, key)

    return dict(trans=trans)


@app.context_processor
def inject_settings():
    currency = session.get('currency', 'GBP')
    return {
        'timeout': session.get('timeout') or 2,
        'first_name': session.get('first_name') or 'User',
        'last_name': session.get('last_name') or 'User',
        'dark_mode': session.get('dark_mode', False),
        'email_notifications': session.get('email_notifications', True),
        'language': session.get('language', 'en'),
        'currency': currency,
        'currency_symbol': CURRENCY_SYMBOLS.get(currency, '£')
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/settings')
def settings():

    """Display current user preferences."""
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User')
    company_name = session.get('company')
    user_email = session.get('email')
    timeout = session.get('timeout')

    if company_name:
        company_display = company_name.replace("_", " ")
    else:
        company_display = None

    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    users_collection = db['users']
    user = users_collection.find_one({"_id": ObjectId(session['user_id'])})

    user_settings = user.get('settings', {})
    settings_data = {
        'dark_mode': user_settings.get('dark_mode', False),
        'timeout': user_settings.get('timeout'),
        'email_notifications': user_settings.get('email_notifications', True),
        'language': user_settings.get('language', 'en'),
        'currency': user_settings.get('currency', 'GBP')
    }

    return render_template(
        'settings.html',
        first_name=user_first_name,
        last_name=user_last_name,
        company=company_display,
        settings=settings_data,
        email=user_email,
        timeout=timeout
    )


@app.route('/save-settings', methods=['POST'])
def save_settings():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {'status': 'error', 'message': 'Expected a JSON object'}, 400

    timeout = data.get('timeout')
    dark_mode = data.get('dark_mode')
    email_notifications = data.get('email_notifications')
    language = data.get('language')
    currency = data.get('currency')

    if timeout is None and dark_mode is None and email_notifications is None and language is None and currency is None:
        return {"status": "error", "message": "No settings provided"}, 400

    if timeout is not None and (type(timeout) is not int or not 1 <= timeout <= 120):
        return {'status': 'error', 'message': 'Timeout must be between 1 and 120 minutes'}, 400
    if any(value is not None and type(value) is not bool for value in [dark_mode, email_notifications]):
        return {'status': 'error', 'message': 'Toggles must be boolean values'}, 400
    if language is not None and (not isinstance(language, str) or language not in TRANSLATIONS):
        return {'status': 'error', 'message': 'Unsupported language'}, 400
    if currency is not None and (not isinstance(currency, str) or currency not in CURRENCY_SYMBOLS):
        return {'status': 'error', 'message': 'Unsupported currency'}, 400

    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    users_collection = db['users']

    update_fields = {}
    if timeout is not None:
        update_fields["settings.timeout"] = timeout
        session['timeout'] = timeout
    if dark_mode is not None:
        update_fields["settings.dark_mode"] = dark_mode
        session['dark_mode'] = dark_mode
    if email_notifications is not None:
        update_fields["settings.email_notifications"] = email_notifications
        session['email_notifications'] = email_notifications
    if language:
        update_fields["settings.language"] = language
        session['language'] = language
    if currency:
        update_fields["settings.currency"] = currency
        session['currency'] = currency

    if update_fields:
        users_collection.update_one(
            {"_id": ObjectId(session['user_id'])},
            {"$set": update_fields}
        )

    return {"status": "success"}, 200



@app.route('/reports')
def reports():
    """Display basic inventory reports and export options."""
    company_name = session.get('company')
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User')

    if not company_name:
        flash("Please log in to access reports.", "error")
        return redirect(url_for('login'))


    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]

    category_summary = list(company_collection.aggregate([
        {"$match": {"asset": True}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]))

    total_assets = sum(item['count'] for item in category_summary)
    total_value = 0
    for asset in company_collection.find({"asset": True}, {"purchase_cost": 1}):
        try:
            total_value += float(asset.get("purchase_cost") or 0)
        except (TypeError, ValueError):
            continue
    total_value = round(total_value, 2)

    return render_template(
        'reports.html',
        first_name=user_first_name,
        last_name=user_last_name,
        company=company_name,
        summary=category_summary,
        total_assets=total_assets,
        total_value=total_value
    )


@app.route('/reports/export/<string:file_format>')
def export_reports(file_format):
    """Export inventory summary reports in CSV or PDF format."""
    company_name = session.get('company')
    if not company_name:
        flash("Please log in to access reports.", "error")
        return redirect(url_for('login'))


    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]

    category_summary = list(company_collection.aggregate([
        {"$match": {"asset": True}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}}
    ]))

    total_assets = sum(item['count'] for item in category_summary)
    total_value = 0
    for asset in company_collection.find({"asset": True}, {"purchase_cost": 1}):
        try:
            total_value += float(asset.get("purchase_cost") or 0)
        except (TypeError, ValueError):
            continue
    total_value = round(total_value, 2)
    currency = session.get('currency', 'GBP')
    symbol = CURRENCY_SYMBOLS.get(currency, '£')

    if file_format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Category', 'Count'])
        for item in category_summary:
            writer.writerow([item['_id'] or 'Uncategorized', item['count']])
        writer.writerow([])
        writer.writerow(['Total Assets', total_assets])
        writer.writerow(['Total Asset Value', f"{symbol}{total_value:.2f}"])
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name='inventory_summary.csv'
        )
    elif file_format == 'pdf':
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 10, txt=f"Total Assets: {total_assets}", ln=True)
        symbol_pdf = pdf_text(symbol)
        pdf.cell(0, 10, txt=f"Total Asset Value: {symbol_pdf}{total_value:.2f}", ln=True)
        pdf.ln(10)
        for item in category_summary:
            category = item['_id'] or 'Uncategorized'
            pdf.cell(0, 10, txt=pdf_text(f"{category}: {item['count']}"), ln=True)
        pdf.ln(10)
        pdf.cell(0, 10, txt=f"Total Assets: {sum(i['count'] for i in category_summary)}", ln=True)
        pdf_output = io.BytesIO()
        pdf_output.write(pdf.output(dest='S').encode('latin1'))
        pdf_output.seek(0)
        return send_file(
            pdf_output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='inventory_summary.pdf'
        )
    else:
        flash('Unsupported report format.', 'error')
        return redirect(url_for('reports'))



@app.route('/logs')
def logs():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User')
    company_name = session.get('company')
    if not company_name:
        return redirect(url_for('login'))
    company_display = company_name.replace('_', ' ')

    try:
        page = max(1, min(1_000_000, int(request.args.get('page', 1))))
    except ValueError:
        page = 1
    per_page = 50
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    query = activity_date_filter(company_name)

    client = mongo.cx
    db = client[app.config['MONGO_DBNAME']]
    cursor = activity_cursor(db, query, skip=(page - 1) * per_page, limit=per_page + 1)
    activities = list(cursor)
    has_next = len(activities) > per_page
    if has_next:
        activities = activities[:-1]

    formatted_activities = []
    for act in activities:
        date = activity_date(act)
        if isinstance(date, datetime):
            date_value = date.strftime('%Y-%m-%d %H:%M:%S')
        elif date:
            date_value = str(date)
        else:
            date_value = 'N/A'
        formatted_activities.append({
            'date': date_value,
            'user': act.get('user', ''),
            'action': act.get('action', ''),
            'asset': activity_label(act),
            'location': act.get('location', '')
        })

    return render_template(
        'logs.html',
        activities=formatted_activities,
        page=page,
        has_next=has_next,
        start_date=start_date_str,
        end_date=end_date_str,
        first_name=user_first_name,
        last_name=user_last_name,
        company=company_display
    )


@app.route('/logs/export')
def export_logs():
    if not session.get('user_id'):
        return redirect(url_for('login'))

    company_name = session.get('company')
    if not company_name:
        return redirect(url_for('login'))

    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    query = activity_date_filter(company_name)

    client = mongo.cx
    db = client[app.config['MONGO_DBNAME']]
    cursor = activity_cursor(db, query)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', size=12)
    pdf.cell(0, 10, txt='Activity Logs', ln=True)
    pdf.ln(5)
    for act in cursor:
        date = activity_date(act)
        if isinstance(date, datetime):
            date_str = date.strftime('%Y-%m-%d %H:%M:%S')
        elif date:
            date_str = str(date)
        else:
            date_str = 'N/A'
        line = f"{date_str} - {act.get('user', '')} - {act.get('action', '')} - {activity_label(act)} - {act.get('location', '')}"
        pdf.multi_cell(0, 8, pdf_text(line))

    pdf_output = io.BytesIO()
    pdf_output.write(pdf.output(dest='S').encode('latin1'))
    pdf_output.seek(0)
    return send_file(
        pdf_output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='activity_logs.pdf'
    )



@app.route('/profile')
def profile_page():
    user_first_name = session.get('first_name', 'User') 
    user_last_name = session.get('last_name', 'User') 
    company_name = session.get('company', None)
    user_email = session.get('email')
    
    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    users_collection = db['users']
    
    return render_template(
        'profile-page.html',
        first_name=user_first_name,
        last_name=user_last_name,
        company=company_name,
        email=user_email
    )



@app.route('/update-profile', methods=['POST'])
def update_profile():
    if not session.get('user_id'):
        return {"status": "unauthorized"}, 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {'status': 'error', 'message': 'Expected a JSON object'}, 400
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')

    if not all(isinstance(value, str) and value.strip() for value in [first_name, last_name, email]) or not valid_email(email.strip()):
        return {"status": "error", "message": "Missing fields"}, 400
    first_name, last_name, email = first_name.strip(), last_name.strip(), email.strip().lower()

    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    users_collection = db['users']

    duplicate = users_collection.find_one({**email_query(email), '_id': {'$ne': ObjectId(session['user_id'])}})
    if duplicate:
        return {'status': 'error', 'message': 'Email address is already in use'}, 400

    users_collection.update_one(
        {"_id": ObjectId(session['user_id'])},
        {"$set": {
            "first_name": first_name,
            "last_name": last_name,
            "email": email
        }}
    )

    # Update session to reflect new data
    session['first_name'] = first_name
    session['last_name'] = last_name
    session['email'] = email

    return {"status": "success"}, 200



@app.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    try:
        # Directly connect using MongoClient
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        users_collection = db['users']  # Access 'users' collection directly
        if request.method == 'POST':
            first_name = request.form.get('first-name', '').strip()
            last_name = request.form.get('last-name', '').strip()
            company = request.form.get('company', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirmation = request.form.get('confirm-password', '')
            if not all([first_name, last_name, company]) or not valid_email(email) or not valid_password(password, confirmation):
                flash('Enter all fields, a valid email, and matching passwords with at least six characters and an uppercase letter.', 'signup-error')
                return render_template('sign-up.html'), 400
            if '\x00' in company or '$' in company or company.startswith('system.') or company in {'users', 'activities', 'fs.files', 'fs.chunks'}:
                flash('Please choose a different company name.', 'signup-company-error')
                return render_template('sign-up.html'), 400

            # Check if the email or company already exists in the database
            existing_user = users_collection.find_one(email_query(email))
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
                'password': hashed_password,
                'settings': {
                    'timeout': 2,  # timeout set to 2 minutes
                    'currency': 'GBP'  # timeout set to 2 minutes 
                }
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
                # Do not leave an unusable account if its company initialization failed.
                if 'user_insert' in locals():
                    users_collection.delete_one({'_id': user_insert.inserted_id})
                app.logger.error('Account creation failed (%s)', type(e).__name__)
                flash('Account creation failed. Please try again later.', 'signup-error')
                return redirect(url_for('sign_up'))

        return render_template('sign-up.html')

    except Exception as e:
        app.logger.error('Account database request failed (%s)', type(e).__name__)
        flash("MongoDB connection failed. Please try again later.", "signup-error")
        return render_template('sign-up.html'), 503




@app.route('/login', methods=['GET', 'POST'])
def login():
    session.permanent = False
   
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        users_collection = db['users']
        user = users_collection.find_one(email_query(email)) if email and password else None

        if user and user.get('password') and check_password_hash(user['password'], password):
            session.clear()
            session['user_logged_in'] = True
            session['user_id'] = str(user['_id'])  # Store user ID in session
            session['first_name'] = user.get('first_name') or 'User'
            session['last_name'] = user.get('last_name') or 'User'
            session['email'] = user['email']
            session['company'] = user['company']
             # Get timeout from user document
            timeout_minutes = user.get('settings', {}).get('timeout', 2) or 2
            session['timeout'] = timeout_minutes
            session['dark_mode'] = user.get('settings', {}).get('dark_mode', False)
            session['email_notifications'] = user.get('settings', {}).get('email_notifications', True)
            session['language'] = user.get('settings', {}).get('language', 'en')
            session['currency'] = user.get('settings', {}).get('currency', 'GBP')
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
      
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        email = request.form.get('email', '').strip().lower()
        if not valid_email(email):
            flash('Enter a valid email address.', 'reset-password-message-error')
            return render_template('forgot-password.html'), 400
        users_collection = db['users']
        user = users_collection.find_one(email_query(email))
        
        
        if user:
            # Generate a token for password reset
            email = user['email']
            token = email_service.generate_token(email, user['password'])
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
    db = mongo.cx[app.config['MONGO_DBNAME']]
    user = db.users.find_one(email_query(email)) if email else None
    if not user or not email_service.verify_token(token, password_hash=user.get('password', '')):
        flash("The password reset link is invalid or has expired.", 'password-update-expired')
        return redirect(url_for('login'))

    if request.method == "POST":
        new_password = request.form.get('password', '')
        if not valid_password(new_password, request.form.get('confirm-password', '')):
            flash('Enter matching passwords with at least six characters and an uppercase letter.', 'reset-error')
            return render_template('reset-password.html', token=token), 400
        hashed_password = generate_password_hash(new_password)
        
        # Update the password in the database
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        users_collection = db['users']
        result = users_collection.update_one({'_id': user['_id'], 'password': user['password']}, {'$set': {'password': hashed_password}})
        if result.matched_count != 1:
            flash('The password reset link is invalid or has expired.', 'password-update-expired')
            return redirect(url_for('login'))
        session.clear()
        
        flash("Your password has been updated successfully.", 'password-update-success')
        return redirect(url_for('login'))
    
    return render_template("reset-password.html", token=token)



@app.route('/inventory')
def inventory_app():
    # Get the first name and company name from the session
    user_first_name = session.get('first_name', 'User')  # Default to 'User' if no first name is found in session
    user_last_name = session.get('last_name', 'User') 
    company_name = session.get('company', 'No Company')  # Default to 'No Company' if no company is found in session
    timeout = session.get('timeout')
    
    # Replace underscores with spaces in the company name
    
    # Debugging: print session data and modified company name
    
    # Render the template with first name and company name
    return render_template('inventory.html', first_name=user_first_name,last_name=user_last_name, company=company_name, timeout=timeout)


@app.route('/dashboard')
def dashboard():
    company_name = session.get('company')
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name','User')

    if not company_name:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('login'))


    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]

    total_assets = company_collection.count_documents({"asset": True})
    categories = list(company_collection.find({"category": True}))  # Fetch real categories
    locations = list(company_collection.find({"location": True}))   # Fetch locations

    recent_assets = list(company_collection.find({"asset": True}).sort("_id", -1).limit(5))

    recent_activities_cursor = activity_cursor(db, {'company': company_name}, limit=5)

    formatted_activities = []
    for act in recent_activities_cursor:
        formatted_activities.append({
            "date": activity_date(act).strftime('%Y-%m-%d %H:%M:%S') if isinstance(activity_date(act), datetime) else str(activity_date(act) or 'N/A'),
            "user": act.get("user"),            
            "action": act.get("action"),
            "asset": activity_label(act),
            "location": act.get("location", "N/A")
        })

    return render_template(
        "dashboard.html",
        first_name=user_first_name,
        last_name=user_last_name,
        company=company_name,
        total_assets=total_assets,
        categories=categories,
        locations=locations,
        recent_assets=recent_assets,
        recent_activities=formatted_activities
    )



def log_activity(action, asset_id, asset_tag, location=None):
    """Logs the activity to the 'activities' collection"""
    user_name = session.get('first_name', 'Unknown User')
    company_name = session.get('company')
    timestamp = datetime.now()

    client = mongo.cx
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

    activities_collection.insert_one(activity_data)


@app.route('/test-mongo')
def test_mongo():
    try:
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        client.admin.command('ping')
        return 'Connected to MongoDB!', 200
    except Exception as e:
        app.logger.error('Database readiness check failed (%s)', type(e).__name__)
        return 'Database connection unavailable', 503


@app.route("/assets")
def assets():
    # Debugging: Check the session data

    # Get the first name from the session, if available
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User') 
    company_name = session.get('company', 'No Company')


    # Fetch assets from the database as before
    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    
      # Access the company's asset collection
    company_collection = db[company_name]

    # Fetch only assets where "asset" is True
    all_assets = list(company_collection.find({"asset": True}))
    
    # Pass the assets and first name to the template
    return render_template("assets.html", assets=all_assets, first_name=user_first_name,last_name=user_last_name, company=company_name)





@app.route("/search")
def search_assets_route():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('assets'))

    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User')
    company_name = session.get('company', 'No Company')

    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]

    matching_assets = list(company_collection.find({
        "asset": True,
        "asset_tag": {"$regex": re.escape(query), "$options": "i"}
    }))

    return render_template(
        "assets.html",
        assets=matching_assets,
        first_name=user_first_name,
        last_name=user_last_name,
        company=company_name
    )


@app.route('/search_assets')
def search_assets():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    company_name = session.get('company')
    if not company_name:
        return jsonify([])

    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]

    results = company_collection.find(
        {"asset": True, "asset_tag": {"$regex": re.escape(query), "$options": "i"}},
        {"asset_tag": 1}
    ).limit(3)

    suggestions = [{"asset_tag": r["asset_tag"], "id": str(r["_id"])} for r in results]
    return jsonify(suggestions)




@app.route("/new-asset")
def new_asset():
     user_first_name = session.get('first_name', 'User') 
     user_last_name = session.get('last_name', 'User') 
     company_name = session.get('company', None)

     client = mongo.cx
     db = client[app.config["MONGO_DBNAME"]]

     company_collection = db[company_name]
     
     locations = list(company_collection.find({"location": True}))
     categories = list(company_collection.find({"category": True}))
     
     return render_template("new-asset.html",first_name=user_first_name,last_name=user_last_name, company=company_name, locations=locations, categories=categories )




@app.route('/save_asset', methods=['POST'])
def save_asset():
    company_name = session.get('company')
    if not company_name:
        flash("No company found in session. Please log in again.", "error")
        return redirect(url_for('login'))

    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]
    fs = gridfs.GridFS(db)

    asset_id = request.form.get('asset_id')
    asset_tag = request.form.get('asset-tag', '').strip()
    serial = request.form.get('serial', '').strip()
    model = request.form.get('model', '').strip()
    notes = request.form.get('notes', '').strip()
    warranty = request.form.get('warranty', '').strip()
    order_number = request.form.get('order-number', '').strip()
    purchase_cost = request.form.get('purchase-cost', '').strip()
    purchase_cost = purchase_cost.replace('£', '').replace('$', '').replace('€', '').strip()
    purchase_date = request.form.get('purchase-date', '').strip()
    location = request.form.get('location', '').strip()
    category = request.form.get('category', '').strip()

    if not asset_tag or not category:
        flash('Asset tag and category are required.', 'error')
        return redirect(url_for('new_asset')) if not asset_id else redirect(url_for('asset_properties', asset_id=asset_id))
    if purchase_cost:
        try:
            amount = Decimal(purchase_cost.replace(',', ''))
            if not amount.is_finite() or amount < 0 or not math.isfinite(float(amount)):
                raise InvalidOperation
            purchase_cost = format(amount, 'f')
        except (InvalidOperation, ValueError, OverflowError):
            return 'Purchase cost must be a non-negative number', 400
    for value in [purchase_date, warranty]:
        if value:
            try:
                datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                return 'Enter a valid date in YYYY-MM-DD format', 400
    duplicate_query = {'asset': True, 'asset_tag': {'$regex': '^' + re.escape(asset_tag) + '$', '$options': 'i'}}
    if asset_id:
        duplicate_query['_id'] = {'$ne': ObjectId(asset_id)}
    if company_collection.find_one(duplicate_query):
        flash('An asset with this tag already exists.', 'error')
        return redirect(url_for('assets'))

    image_file = request.files.get('image')
    image_id = None

    if image_file and image_file.filename != "":
        if image_file.mimetype not in {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}:
            return 'Upload a PNG, JPEG, GIF, or WebP image', 400
        try:
            filename = secure_filename(image_file.filename)
            image_id = fs.put(
                image_file,
                filename=filename,
                content_type=image_file.mimetype,
                company=company_name,
                uploaded_by=session.get('first_name'),
                asset_tag=asset_tag,
                timestamp=datetime.now()
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
            delete_unused_image(company_collection, g.item.get('image_id'))
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

        if session.get('email_notifications', True):
            subject = f"Asset {asset_tag} {action.lower()}d"
            html_content = (
                f"<p>The asset <strong>{escape(asset_tag)}</strong> was {action.lower()}d in {escape(company_name)}.</p>"
            )
            email_service.send_email(
                session.get('email'),
                subject,
                html_content
            )

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

        mimetype = image_file.metadata.get('content_type') if image_file.metadata else None
        # Older uploads used GridFS's deprecated contentType field.
        mimetype = mimetype or image_file._file.get('contentType') or 'application/octet-stream'
        response = send_file(image_file, mimetype=mimetype, as_attachment=mimetype not in {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}, download_name=image_file.filename or 'image')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    except Exception as e:
        return 'Image not found', 404




@app.route('/asset-properties')
def asset_properties():
    asset_id = request.args.get('asset_id')  # Get asset ID from URL
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User') 
    company_name = session.get('company', None)

    if asset_id:
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[session.get('company', 'default_company')]
        locations = list(company_collection.find({"location": True}))
        categories = list(company_collection.find({"category": True}))

        asset = company_collection.find_one({"_id": ObjectId(asset_id)})  # Fetch asset

        if asset:
            return render_template("asset-properties.html", asset=asset,first_name=user_first_name,last_name=user_last_name, locations=locations, company=company_name ,categories=categories)  

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

        # Connect to MongoDB
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[company_name]

        asset = company_collection.find_one({"_id": ObjectId(asset_id)})

        if not asset:
            flash("Asset not found!", "danger")
            return redirect(url_for('assets'))

        # Attempt to find and delete the asset
        result = company_collection.delete_one({"_id": ObjectId(asset_id)})

        if result.deleted_count > 0:
            delete_unused_image(company_collection, asset.get('image_id'))
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
    
    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    user_first_name = session.get('first_name', 'User') 
    user_last_name = session.get('last_name', 'User') 
    company_name = session.get('company', None)
    company_collection = db[company_name]

    # Fetch asset details from the database using the provided asset_id
    asset = company_collection.find_one({"_id": ObjectId(asset_id)})

    # Pair labels and values
    labels = [
        'Asset Name', 'Model', 'Serial', 'Location', 'Category', 'Purchase Date', 'Purchase Cost'
    ]
    currency = session.get('currency', 'GBP')
    symbol = CURRENCY_SYMBOLS.get(currency, '£')
    purchase_cost = asset.get('purchase_cost')
    values = [
       asset.get('asset_tag'),
        asset.get('model'),
        asset.get('serial'),
        asset.get('location'),
        asset.get('category'),
        asset.get('purchase_date'),
        f"{symbol}{purchase_cost}" if purchase_cost not in (None, '') else 'N/A'
    ]
    labels_values = list(zip(labels, values))

    return render_template('view-asset.html', asset=asset, company=company_name, labels_values=labels_values, first_name=user_first_name, last_name=user_last_name,)



        

@app.route('/locations')
def locations():
    # Debugging: Check the session data

    # Get the first name from the session, if available
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User') 
    company_name = session.get('company', 'No Company')


    # Fetch assets from the database as before
    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    
      # Access the company's asset collection
    company_collection = db[company_name]

    # Fetch only assets where "asset" is True
    all_locations = list(company_collection.find({"location": True}))
    
    # Pass the assets and first name to the template
    return render_template("locations.html", locations=all_locations, first_name=user_first_name,last_name=user_last_name, company=company_name)




@app.route('/new-location')
def new_location():
    company_name = session.get('company', None)
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User') 

    
    if request.args.get("modal") == "true":
        # Render only the form part for use in a modal
        return render_template("location_modal_form.html", first_name=user_first_name,last_name=user_last_name, company=company_name)
    
    return render_template("new-location.html",first_name=user_first_name, company=company_name )




@app.route('/save-location', methods=['POST'])
def save_location():
    company_name = session.get('company')
    if not company_name:
        flash("No company found in session. Please log in again.", "error")
        return redirect(url_for('login'))

    # Check if the request is from the modal
    is_modal = request.args.get('modal') == 'true'
    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]

    # Get form data
    location_id = request.form.get('location_id')
    location_tag = request.form.get('location-tag', '').strip()
    if not location_tag:
        return 'Location name is required', 400
    phone = request.form.get('phone', '').strip()
    address = request.form.get('address', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    post_code = request.form.get('post-code', '').strip()

    # Prevent duplicate location tags (case-insensitive)
    query = {"location": True, "location_tag": {"$regex": "^" + re.escape(location_tag) + "$", "$options": "i"}}
    if location_id:
        query["_id"] = {"$ne": ObjectId(location_id)}

    existing = company_collection.find_one(query)
    if existing:
        if is_modal:
            return '''
                <script>
                    alert("A location with this name already exists.");
                    window.history.back();
                </script>
            '''
        else:
            flash("A location with this name already exists.", "error")
            if location_id:
                return redirect(url_for('location_properties', location_id=location_id))
            else:
                return render_template(
                    "new-location.html",
                    location={"location_tag": location_tag, "phone": phone, "address": address, "city": city, "state": state, "post_code": post_code},
                    first_name=session.get('first_name', 'User'),
                    company=company_name
                )

    # Location data
    location_data = {
        'location': True,
        'location_tag': location_tag,
        'phone': phone,
        'address': address,
        'city': city,
        'state': state,
        'post_code': post_code
    }

    try:
        # Save location (insert or update)
        if location_id:
            company_collection.update_one(
                {"_id": ObjectId(location_id)},
                {"$set": location_data}
            )
            if g.item['location_tag'] != location_tag:
                company_collection.update_many({'asset': True, 'location': g.item['location_tag']}, {'$set': {'location': location_tag}})
            action = 'Update Location'
        else:
            company_collection.insert_one(location_data)
            action = 'Create Location'

        # Log the activity
        db.activities.insert_one({
            'timestamp': datetime.now(),
            'user': session.get('first_name'),
            'action': action,
            'location': location_tag,
            'company': company_name
        })

        # Handle modal response
        if is_modal:
            return render_template('modal_saved.html', kind='location', name=location_tag)
        else:
            flash("Location saved successfully!", "success")
            return redirect(url_for('locations'))

    except Exception as e:
        # Handle error
        if is_modal:
            return f"<script>alert('An error occurred: {str(e)}');</script>"
        flash(f"An error occurred while saving the location: {str(e)}", "error")
        return redirect(url_for('dashboard'))




@app.route('/location-properties')
def location_properties():
    
    location_id = request.args.get('location_id')  # Get location ID from URL
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User')
    company_name = session.get('company', 'Not Available')
    if location_id:
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[session.get('company', 'default_company')]

        
        location = company_collection.find_one({"_id": ObjectId(location_id)})  # Fetch location

        if location:
            
            return render_template(
                "location-properties.html",
                location=location,
                first_name=user_first_name,
                last_name=user_last_name,
                company=company_name,
            )

    
    return render_template(
        "location-properties.html",
        location=None,
        first_name=user_first_name,
        last_name=user_last_name,
        company=company_name,
    )  # If no location ID, load empty form



@app.route('/delete_location/<location_id>', methods=['POST'])
def delete_location(location_id):
    try:
        # Get the company name from session
        company_name = session.get('company', None)
        if not company_name:
            flash("No company found in session. Please log in again.", "error")
            return redirect(url_for('login'))

        # Replace underscores with spaces in company name (if needed)

        # Connect to MongoDB
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[company_name]

        location = company_collection.find_one({"_id": ObjectId(location_id)})

        if not location:
            flash("Location not found!", "danger")
            return redirect(url_for('locations'))

        if company_collection.count_documents({'asset': True, 'location': location['location_tag']}):
            flash('Move assets to another location before deleting this location.', 'error')
            return redirect(url_for('locations'))

        # Attempt to find and delete the asset
        result = company_collection.delete_one({"_id": ObjectId(location_id)})

        if result.deleted_count > 0:
            # Log the delete activity
            activity_data = {
                'timestamp': datetime.now(),
                'user': session['first_name'],
                'action': 'Delete Location',
                'company': company_name,
                'location': location.get('location_tag', 'Unknown location')
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

    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User') 
    company_name = session.get('company', 'No Company')

    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]  

    # Fetch all categories for this company
    all_categories = list(company_collection.find({"category": True}))

    # Count items per category by matching category name
    for category in all_categories:
        category_name = category["name"]
        item_count = company_collection.count_documents({
            'asset': True,
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
        last_name=user_last_name,
        company=company_name
    )




@app.route('/new-category')
def new_category():
    company_name = session.get('company', None)
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User') 

    if request.args.get("modal") == "true":
        # Render only the form part for use in a modal
        return render_template("category_modal_form.html", first_name=user_first_name, company=company_name)
    
    # Otherwise, render the full page with layout
    return render_template("new-category.html", first_name=user_first_name,last_name=user_last_name, company=company_name)




@app.route('/save_category', methods=['POST'])
def save_category():
    company_name = session.get('company')
    if not company_name:
        flash("No company found in session. Please log in again.", "error")
        return redirect(url_for('login'))

    is_modal = request.args.get('modal') == 'true'
    client = mongo.cx
    db = client[app.config["MONGO_DBNAME"]]
    company_collection = db[company_name]
    fs = gridfs.GridFS(db)

    category_id = request.form.get('category_id')
    category_name = request.form.get('category-name', '').strip()
    if not category_name:
        return 'Category name is required', 400
    category_type = request.form.get('category-type', '').strip()

    # Prevent duplicate category names (case-insensitive)
    query = {"category": True, "name": {"$regex": "^" + re.escape(category_name) + "$", "$options": "i"}}
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
        if image_file.mimetype not in {'image/png', 'image/jpeg', 'image/gif', 'image/webp'}:
            return 'Upload a PNG, JPEG, GIF, or WebP image', 400
        try:
            filename = secure_filename(image_file.filename)
            image_id = fs.put(
                image_file,
                filename=filename,
                content_type=image_file.mimetype,
                company=company_name,
                uploaded_by=session.get('first_name'),
                category_name=category_name,
                timestamp=datetime.now()
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
            if g.item['name'] != category_name:
                company_collection.update_many({'asset': True, 'category': g.item['name']}, {'$set': {'category': category_name}})
            action = 'Update Category'
            delete_unused_image(company_collection, g.item.get('image_id'))
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
            return render_template('modal_saved.html', kind='category', name=category_name)
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
    user_first_name = session.get('first_name', 'User')
    user_last_name = session.get('last_name', 'User')
    company_name = session.get('company', 'Not Available')
    if category_id:
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[session.get('company', 'default_company')]

        category = company_collection.find_one({
            "_id": ObjectId(category_id),
            "category": True
        })  # Ensure it's actually a category

        if category:
            
            return render_template(
                "category-properties.html",
                category=category,
                first_name=user_first_name,
                last_name=user_last_name,
                company=company_name,
            )

    # If no valid ID or not found, load empty template
    
    return render_template(
        "category-properties.html",
        category=None,
        first_name=user_first_name,
        last_name=user_last_name,
        company=company_name,
    )



@app.route('/delete_category/<category_id>', methods=['POST'])
def delete_category(category_id):
    try:
        # Get the company name from session
        company_name = session.get('company', None)
        if not company_name:
            flash("No company found in session. Please log in again.", "error")
            return redirect(url_for('login'))


        # Connect to MongoDB
        client = mongo.cx
        db = client[app.config["MONGO_DBNAME"]]
        company_collection = db[company_name]

        # Find the category
        category = company_collection.find_one({"_id": ObjectId(category_id), "category": True})

        if not category:
            flash("Category not found!", "danger")
            return redirect(url_for('categories'))

        if company_collection.count_documents({'asset': True, 'category': category['name']}):
            flash('Move assets to another category before deleting this category.', 'error')
            return redirect(url_for('categories'))

        # Delete the category
        result = company_collection.delete_one({"_id": ObjectId(category_id)})

        if result.deleted_count > 0:
            # Log the delete activity
            delete_unused_image(company_collection, category.get('image_id'))
            activity_data = {
                'timestamp': datetime.now(),
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
            debug=os.environ.get('FLASK_DEBUG') == '1')
