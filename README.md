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
- **Account Management** – Sign‑up, log in/out and password reset via email (SendGrid).
- **Dashboard** – Displays asset count, categories, locations, recent assets and activities.
- **Assets** – Create, view, update and delete assets with optional image upload.
- **Categories** – Manage asset categories. Duplicate names are prevented.
- **Locations** – Track locations where assets are stored. Duplicate tags are prevented.
- **Settings** – Update profile information and set an idle logout time in minutes.
- **Search and Filters** – Pages include lists with actions to edit or delete items.

## Technologies Used
- **Python 3** with **Flask** for the web framework
- **MongoDB** and **PyMongo** for the database
- **GridFS** for image storage
- **SendGrid** for transactional emails
- HTML5, CSS3 and basic JavaScript for the front end

Dependencies are listed in [`requirements.txt`](requirements.txt).

## Database
MongoDB stores user accounts in the `users` collection and each company gets its own collection for assets, categories and locations. An additional `activities` collection keeps a history of actions performed by users. Images are stored using GridFS.

## Deployment
The project is configured for deployment on a platform such as Render or Heroku using the provided `Procfile`.
Environment variables required:
- `MONGO_URI` – connection string for MongoDB
- `MONGO_DBNAME` – database name
- `SECRET_KEY` – Flask secret key
- `SENDGRID_API_KEY` and `MAIL_DEFAULT_SENDER` – for password reset emails

## Installation
1. Clone the repository:
   ```bash
   git clone <repo-url>
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set the environment variables listed above.
4. Run the application locally:
   ```bash
   python app.py
   ```
   The site will be available at `http://localhost:5000`.

## Testing
The application was manually tested using different user flows:
- Creating an account and verifying duplicate checks
- Logging in with valid and invalid credentials
- Adding, editing and deleting assets, categories and locations
- Resetting a password via email token
- Adjusting the idle timeout in settings

Basic syntax checks were performed with `python -m py_compile`.

## Credits
This project was developed for educational purposes with the Code Institute. Images and icons are from open source resources. Special thanks to the Code Institute community for guidance and support.