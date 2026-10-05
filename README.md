# Assety

Assety is an inventory and asset management web application built with Flask and MongoDB. The project was created as part of the Code Institute Diploma in Full Stack Software Development (Milestone Project 3).

## Table of Contents
- [Project Goals](#project-goals)
- [UX](#ux)
  - [User Stories](#user-stories)
  - [Design](#design)
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Database](#database)
- [Deployment](#deployment)
- [Installation](#installation)
- [Testing](#testing)
  - [Jest Unit Tests](#jest-unit-tests)
  - [Manual Testing](#manual-testing)
- [Credits](#credits)

## Project Goals
The goal of Assety is to provide small businesses with an easy way to track company assets. Users can create an account, log in and manage assets, categories and locations. Additional features include dashboard statistics, user profiles, password reset via email and configurable idle logout.

## UX
### User Stories
1. **New Visitor**
   - I want to understand what the site offers so that I can decide if it suits my needs.
   - I want to sign up for a free account so that I can try the application.
2. **Returning User**
   - I want to log in securely so that I can manage my inventory.
   - I want to recover my password if I forget it.
3. **Authenticated User**
   - I want to add new assets, categories and locations.
   - I want to edit or delete existing records.
   - I want a dashboard that summarises recent activity and totals.
   - I want to update my profile and adjust the inactivity timeout.

### Design
The application uses a simple interface built with HTML templates and a custom CSS file. The landing page highlights key benefits and provides links to sign up or log in. Once logged in, users see the dashboard with quick links to assets, categories and locations.

## Features
Assety offers a range of tools to simplify asset tracking:


- **Dashboard** – Displays asset counts, recent assets, recent activities and quick links.
- **Asset Management** – Create, update and delete assets with optional image uploads stored in MongoDB GridFS.
- **Categories & Locations** – Maintain reusable lists for categorising and locating assets.
- **Search** – Find assets by tag with live search suggestions.
- **User Profiles** – Update name and email from the profile page.
- **Settings** – Toggle dark mode and configure an idle timeout to control automatic logouts.
- **Activity Log** – Records asset changes for review on the dashboard.
- **Email Notifications** – Receive password reset and asset change emails when enabled.

## Technologies Used
- **Python & Flask** for the web application framework
- **MongoDB** with Flask‑PyMongo and **GridFS** for data and file storage
- **HTML**, **CSS** and **JavaScript** for the front end
- **Jest** for client‑side unit testing
- **SendGrid** for password reset emails

## Database
MongoDB powers the application's persistence layer and separates data by company.

### Page Relationships
- **Dashboard** – Pulls overall asset counts and recent items from the company collection while reading recent activity from the global `activities` collection.
- **Assets Page** – Creates and updates documents flagged with `asset: true` inside the company collection. Each asset embeds the chosen `category` and `location` names and may reference an image stored in GridFS.
- **Categories Page** – Manages documents marked with `category: true` in the same collection. These categories are reused when creating assets.
- **Locations Page** – Handles documents marked with `location: true` so assets can be assigned physical locations.
- **Search & Dashboard Widgets** – Query the company collection for asset tags, categories and locations to provide live suggestions and summary charts.
- **Profile/Settings** – Reads and writes the user's record in the `users` collection, including configurable settings such as the idle timeout, dark mode preference, email notifications and language.
- **Activity Log** – Displays entries from the `activities` collection, each linked to a user, company and optional `asset_id`.

### General Relationships
- Every entry in the `users` collection includes a `company` field; that name determines which company‑specific collection the user interacts with after logging in.
- Company collections store mixed document types distinguished by flags (`asset`, `category`, `location`). Assets reference categories and locations by name, simplifying queries while keeping related metadata in one place.
- The `activities` collection acts as a cross‑company audit trail, storing the action performed, the company and any related asset identifier for display on dashboards and logs.
## Technologies Used
- **Python & Flask** for the web application framework
- **MongoDB** with Flask‑PyMongo and **GridFS** for data and file storage
- **HTML**, **CSS** and **JavaScript** for the front end
- **Jest** for client‑side unit testing
- **SendGrid** for password reset emails

## Database
MongoDB stores user accounts in the `users` collection. Each company has its own collection that holds assets as well as category and location documents (flagged by `category: true` or `location: true`). An additional `activities` collection logs actions for the dashboard.

## Installation
Use Python 3.12 (pinned in `.python-version`) and Node.js 24 for the browser tests.
Create and activate a virtual environment, then install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows CMD: .venv\Scripts\activate
pip install -r requirements.txt
npm ci
```

Configure these values in your local environment or Heroku Config Vars:

| Variable | Purpose |
| --- | --- |
| `MONGO_URI` | MongoDB connection string. For a local server: `mongodb://127.0.0.1:27017/assety_dev`. Use your Atlas connection string on Heroku. |
| `MONGO_DBNAME` | Database name. Optional when the URI includes it; this is the database name, not the cluster name. |
| `SECRET_KEY` | A private, stable random signing key. Required on Heroku; the app uses a temporary random key for local development when unset. |
| `SENDGRID_API_KEY` | Optional SendGrid credential for password recovery and asset notification emails. |
| `MAIL_DEFAULT_SENDER` | Optional verified SendGrid sender address; required when enabling email delivery. |

Generate a signing key locally with `python -c "import secrets; print(secrets.token_hex(32))"` and enter it securely in Heroku Config Vars. Never commit or share the key or a MongoDB URI containing credentials. Local development sessions reset when the temporary signing key changes.

Start MongoDB, then run `python app.py`. The development server listens on port 5000; set `FLASK_DEBUG=1` only when you want local debugging.

### Heroku

The `Procfile` starts Gunicorn and binds to Heroku's assigned `PORT`; it does not use Flask's development server. Before deploying, configure `MONGO_URI`, the database name (in the URI or `MONGO_DBNAME`), and `SECRET_KEY`. The Atlas database user and network access rules must permit connections from Heroku. Configure SendGrid only if you need email delivery.

After deployment, inspect startup errors with `heroku logs --tail --app YOUR_APP_NAME`. Changing the signing key invalidates existing sessions and password reset links. Users should sign in again after upgrading from the old hardcoded key.

Company names are used verbatim as MongoDB collection keys, including underscores. This update does not migrate historical records. If an older version wrote an underscore company's records into a separate collection with spaces, inspect those collections and their ownership before migrating any data.

## Testing

### Jest Unit Tests
Client-side password validation is covered by a Jest suite located in `static/scripts/script.test.js`.
The tests run in the `jsdom` environment so that browser APIs such as `document` are available.

Install Node.js dependencies and run the tests with:

```bash
npm ci
npm test
```

The suite verifies that the validation UI appears only once, toggles the submit button as criteria are met,
keeps rules hidden until the user interacts with the fields, shows all rules on password focus and warns
when the two password fields do not match. It also checks login/reset page compatibility and the idle warning, stay-logged-in action, and logout countdown.

### Python integration tests

With a MongoDB server running locally, run:

```bash
python -m unittest discover -s tests -v
```

The tests create a uniquely named temporary database, then remove it. They use `mongodb://127.0.0.1:27017` by default; set `ASSETY_TEST_MONGO_URI` only to a MongoDB server intended for tests. They do not use the application's configured production database or send email.

Coverage includes authentication, signup/login/password recovery, settings/profile validation, company isolation, asset/image handling, category/location edits and deletion, literal search, activity-log filtering and pagination, PDF exports, and Heroku startup configuration. PDFs use FPDF's built-in fonts: supported Windows-1252 characters (including currency symbols) are preserved; unsupported glyphs are replaced rather than crashing the export.

### Manual Testing
The application was manually tested using different user flows:
- Creating an account and verifying duplicate checks
- Logging in with valid and invalid credentials
- Adding, editing and deleting assets, categories and locations
- Resetting a password via email token
- Adjusting the idle timeout, dark mode, email notifications, and language in settings

Basic syntax checks were performed with `python -m py_compile`.

## Credits
This project was developed for educational purposes with the Code Institute. Images and icons are from open source resources. Special thanks to the Code Institute community for guidance and support.
