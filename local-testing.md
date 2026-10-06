# Local testing on Windows

This checkout came from `Bonzay993/Assety` at `c0710b6`. The handoff patch
was absent, passed its application check, and was applied on the local
`codex/local-testing` branch. Its initial checkpoint is committed locally;
follow-up changes are recorded in `CHANGELOG.md` and remain local.

## Start and stop

Double-click `start-local.cmd`, then open <http://127.0.0.1:5001>.
Use **Sign Up** to create your own test account. The development database starts
empty; your Heroku accounts and inventory are not copied here.

Double-click `stop-local.cmd` to stop Flask and MongoDB. Your local accounts,
inventory, and uploaded images are retained across restarts.

After editing Python code, stop and start the app again, then refresh the
browser. For CSS or JavaScript edits, refresh the browser (Ctrl+F5 if needed).

You can also run these commands from CMD in this folder:

```cmd
start-local.cmd
stop-local.cmd
test-local.cmd
```

For status, run:

```cmd
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\local.ps1 status
```

The launcher uses Python 3.12 in `.venv`, MongoDB 7.0.43 in
`.local\mongodb`, and `mongodb://127.0.0.1:27019/assety_dev`. Both servers
listen only on this computer. It sets the development connection explicitly,
disables SendGrid, and refuses to start if `env.py` exists because that file
can override database settings. Live email delivery and password-reset emails
require separate configuration and are not available with this launcher.

Local tools, logs, data, signing key, and the original patch live in ignored
`.local`. Never add that folder or `.venv` to Git. Logs are
`.local\flask-error.log`, `.local\flask.log`, and `.local\mongo.log`.

## Automated checks

`test-local.cmd` starts or reuses the local MongoDB server, runs the Python
integration suite and Jest, and retains your `assety_dev` data. The Python
suite creates and removes its own uniquely named temporary database on port
27019. The launcher checks recorded process identity before reusing or stopping
servers; other processes occupying the ports are left alone.

Dependencies are already installed on this computer. To refresh them:

```cmd
.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
```

If the virtual environment is removed, recreate it with Python 3.12 and install
the requirements again. If MongoDB is removed, download the official Windows
7.0.43 ZIP from `https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-7.0.43.zip`,
verify SHA-256 `09b7893dc07fbb6d67d4c2690f6d1fa5b3039a0b3b5de34fb1d9096d55a2230f`,
and extract `bin\mongod.exe` and any adjacent DLLs into `.local\mongodb\bin`.
MongoDB's Windows ZIP setup is described in the [official documentation](https://www.mongodb.com/docs/v7.0/tutorial/install-mongodb-on-windows/).

## Responsive interface checks

The shared responsive stylesheet covers the public pages, account forms,
application navigation, dashboard, asset/category/location lists and forms,
reports, logs, profile, settings, and embedded popup forms. Phones use an
expandable navigation bar and labeled record cards; wider screens use aligned
columns, with scrolling contained inside wide lists when needed.

The responsive pass was checked on 23 application screens at widths of 320, 375, 390,
767, 768, 1024, 1440, and 1920 pixels, including populated records with long
names. Private screens were also checked in dark mode. The latest regression
run passed 50 Python integration tests and 20 JavaScript tests, including
mobile navigation, keyboard dismissal, and changing viewport size. The
refreshed landing page was checked at 390px and 1440px widths; its Pricing link
reaches the plan section, with working signup and sign-in links.

To check changes manually, resize your browser or use its device preview.
Check Menu and the Categories submenu, create/edit forms, record actions,
category/location popups, and light/dark settings. Refresh after CSS changes;
stop/start the local app after template changes.

## Changing an account email

Settings includes a separate Change email form. Enter a new email and the
account's current password. Incorrect passwords, invalid addresses, and
addresses already used by another account are rejected. The password field
is cleared after each submission. After saving, sign in with the new email
and the same password. Existing password-reset links for the old email stop
working.

Profile still allows name changes and links to Settings for email changes;
its endpoint cannot bypass the password check. Regression tests cover these
rules in a disposable database, and the form was checked at phone, tablet,
and desktop widths.

## Review before pushing

Test the changes locally, then review with `git diff` and `git status`.
Nothing has been pushed to GitHub or deployed to Heroku. When you approve
the changes, they can be committed and pushed to a GitHub review branch.
Review Heroku's automatic deployment settings before merging into `main`.
