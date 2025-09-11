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

@@ -59,36 +61,53 @@ MongoDB stores user accounts in the `users` collection and each company gets its
- **Dashboard** – Displays asset counts, recent assets, recent activities and quick links.
- **Asset Management** – Create, update and delete assets with optional image uploads stored in MongoDB GridFS.
- **Categories & Locations** – Maintain reusable lists for categorising and locating assets.
- **Search** – Find assets by tag with live search suggestions.
- **User Profiles** – Update name and email from the profile page.
- **Settings** – Toggle dark mode and configure an idle timeout to control automatic logouts.
- **Activity Log** – Records asset changes for review on the dashboard.

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

### Jest Unit Tests
Client-side password validation is covered by a Jest suite located in `static/scripts/script.test.js`.
The tests run in the `jsdom` environment so that browser APIs such as `document` are available.

Install Node.js dependencies and run the tests with:

```bash
npm install
npm test
```

The suite verifies that the validation UI appears only once, toggles the submit button as criteria are met,
keeps rules hidden until the user interacts with the fields, shows all rules on password focus and warns
when the two password fields do not match.

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