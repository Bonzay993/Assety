"""Integration regressions against an isolated, disposable MongoDB database.

Run: python -m unittest discover -s tests -v
Set ASSETY_TEST_MONGO_URI only to a MongoDB server intended for tests.
"""
import io
import os
import subprocess
import sys
import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

from bson import ObjectId
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'assety_test_' + uuid.uuid4().hex
URI = os.environ.get('ASSETY_TEST_MONGO_URI', 'mongodb://127.0.0.1:27017')
os.environ['MONGO_URI'] = URI
os.environ['MONGO_DBNAME'] = DATABASE
os.environ['SECRET_KEY'] = 'isolated-regression-test-secret'

import app as application


class AppRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mongo = MongoClient(URI, serverSelectionTimeoutMS=3000)
        cls.mongo.admin.command('ping')
        cls.db = cls.mongo[DATABASE]
        application.app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls):
        cls.mongo.drop_database(DATABASE)
        cls.mongo.close()

    def setUp(self):
        for collection in self.db.list_collection_names():
            self.db.drop_collection(collection)
        self.client = application.app.test_client()
        self.company = 'Test_Company'
        self.user = {
            'first_name': 'Test', 'last_name': 'User', 'company': self.company,
            'email': 'test@example.invalid', 'password': generate_password_hash('Password123'),
            'settings': {'timeout': 2, 'email_notifications': False},
        }
        self.user['_id'] = self.db.users.insert_one(self.user).inserted_id
        self.db[self.company].insert_one({'company_name': self.company})
        with self.client.session_transaction() as session:
            session.update(user_id=str(self.user['_id']), company=self.company,
                           first_name='Test', last_name='User', email=self.user['email'],
                           timeout=2, email_notifications=False)

    def asset(self, **overrides):
        data = {'asset': True, 'asset_tag': 'Laptop[1]', 'category': 'Computers',
                'location': 'Office', 'purchase_cost': '100.00'}
        data.update(overrides)
        data['_id'] = self.db[self.company].insert_one(data).inserted_id
        return data

    def asset_form(self, **overrides):
        data = {'asset-tag': 'Laptop[1]', 'category': 'Computers', 'location': 'Office',
                'serial': '', 'model': '', 'notes': '', 'warranty': '', 'order-number': '',
                'purchase-cost': '100.00', 'purchase-date': ''}
        data.update(overrides)
        return data

    def test_secret_key_uses_environment(self):
        self.assertEqual(application.app.secret_key, os.environ['SECRET_KEY'])

    def test_database_name_can_be_inferred_from_uri(self):
        environment = os.environ.copy()
        environment.pop('MONGO_DBNAME', None)
        environment['MONGO_URI'] = 'mongodb://127.0.0.1:27017/inferred_database'
        result = subprocess.run([sys.executable, '-c', "import app; assert app.app.config['MONGO_DBNAME'] == 'inferred_database'"], env=environment, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_private_pages_require_login(self):
        anonymous = application.app.test_client()
        for path in ['/profile', '/inventory', '/assets', '/locations', '/categories', '/new-asset',
                     '/new-category', '/new-location', '/asset/' + str(ObjectId()),
                     '/asset-properties', '/location-properties', '/category-properties']:
            with self.subTest(path=path):
                self.assertEqual(anonymous.get(path).status_code, 302)

    def test_stale_session_is_cleared(self):
        self.db.users.delete_one({'_id': self.user['_id']})
        self.assertEqual(self.client.get('/settings').status_code, 302)

    def test_underscore_company_uses_original_collection(self):
        self.asset()
        response = self.client.get('/assets')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Laptop[1]', response.data)

    def test_search_treats_punctuation_as_literal_text(self):
        self.asset()
        response = self.client.get('/search_assets?q=[')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json), 1)
        self.assertEqual(self.client.get('/search?q=[').status_code, 200)

    def test_missing_and_invalid_asset_ids_return_not_found(self):
        for asset_id in ['invalid', str(ObjectId())]:
            with self.subTest(asset_id=asset_id):
                self.assertEqual(self.client.get('/asset/' + asset_id).status_code, 404)
                self.assertEqual(self.client.get('/asset-properties?asset_id=' + asset_id).status_code, 404)

    def test_record_type_cannot_be_changed_by_asset_endpoint(self):
        category_id = self.db[self.company].insert_one({'category': True, 'name': 'Computers'}).inserted_id
        response = self.client.post('/save_asset', data=self.asset_form(asset_id=str(category_id)))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn('asset', self.db[self.company].find_one({'_id': category_id}))

    def test_cross_company_records_are_not_accessible(self):
        asset_id = self.db.OtherCompany.insert_one({'asset': True, 'asset_tag': 'Private'}).inserted_id
        self.assertEqual(self.client.get('/asset/' + str(asset_id)).status_code, 404)
        self.assertEqual(self.client.post('/save_asset', data=self.asset_form(asset_id=str(asset_id))).status_code, 404)

    def test_category_and_location_delete_are_logged(self):
        for kind, name in [('category', 'Computers'), ('location', 'Office')]:
            field = 'name' if kind == 'category' else 'location_tag'
            object_id = self.db[self.company].insert_one({kind: True, field: name}).inserted_id
            response = self.client.post('/delete_' + kind + '/' + str(object_id))
            self.assertEqual(response.status_code, 302)
            self.assertIsNone(self.db[self.company].find_one({'_id': object_id}))
            event = self.db.activities.find_one({'company': self.company, 'action': 'Delete ' + kind.title()})
            self.assertIsNotNone(event)
            self.assertIsInstance(event['timestamp'], datetime)

    def test_activity_dates_and_date_filter_include_current_events(self):
        self.db.activities.insert_one({'company': self.company, 'timestamp': datetime.now(), 'user': 'Test', 'action': 'Create', 'asset': 'CurrentAsset'})
        date = datetime.now().strftime('%Y-%m-%d')
        response = self.client.get('/logs?start_date=' + date + '&end_date=' + date)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'CurrentAsset', response.data)
        self.assertIn(date.encode(), response.data)

    def test_legacy_activity_date_does_not_crash_dashboard(self):
        self.db.activities.insert_one({'company': self.company, 'date': datetime.now(), 'action': 'Delete'})
        self.assertEqual(self.client.get('/dashboard').status_code, 200)

    def test_invalid_pagination_does_not_crash(self):
        for page in ['abc', '-1', '0']:
            with self.subTest(page=page):
                self.assertEqual(self.client.get('/logs?page=' + page).status_code, 200)

    def test_euro_and_unicode_reports_do_not_crash(self):
        self.asset(category='Laptops €', location='București')
        self.db.activities.insert_one({'company': self.company, 'timestamp': datetime.now(), 'user': 'Ștefan', 'action': 'Create', 'asset': 'Laptop €'})
        with self.client.session_transaction() as session:
            session['currency'] = 'EUR'
        for path in ['/reports/export/pdf', '/logs/export']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data.startswith(b'%PDF-'))

    def test_settings_reject_invalid_types_and_values(self):
        for payload in [[], {'timeout': 0}, {'timeout': 'bad'}, {'dark_mode': 'false'},
                        {'currency': 'INVALID'}, {'language': 'invalid'}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/save-settings', json=payload).status_code, 400)
        self.assertEqual(self.db.users.find_one({'_id': self.user['_id']})['settings']['timeout'], 2)

    def test_profile_update_rejects_duplicate_email(self):
        self.db.users.insert_one({'email': 'other@example.invalid', 'company': 'OtherCompany'})
        response = self.client.post('/update-profile', json={'first_name': 'Test', 'last_name': 'User', 'email': 'OTHER@example.invalid'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.users.find_one({'_id': self.user['_id']})['email'], self.user['email'])

    def test_signup_requires_valid_matching_passwords(self):
        response = self.client.post('/sign-up', data={'first-name': 'A', 'last-name': 'B', 'company': 'NewCompany', 'email': 'new@example.invalid', 'password': 'short', 'confirm-password': 'different'})
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.db.users.find_one({'email': 'new@example.invalid'}))

    def test_login_accepts_case_insensitive_email(self):
        anonymous = application.app.test_client()
        response = anonymous.post('/login', data={'email': 'TEST@EXAMPLE.INVALID', 'password': 'Password123'})
        self.assertEqual(response.status_code, 302)

    def test_missing_password_does_not_crash_login(self):
        anonymous = application.app.test_client()
        self.assertEqual(anonymous.post('/login', data={'email': self.user['email']}).status_code, 200)

    def test_forgot_password_works_with_notifications_disabled(self):
        with patch.object(application.email_service, 'send_email', return_value=object()) as send:
            response = self.client.post('/forgot-password', data={'email': self.user['email']})
        self.assertEqual(response.status_code, 200)
        send.assert_called_once()

    def test_password_reset_get_does_not_flash_an_error(self):
        token = application.email_service.generate_token(self.user['email'], self.user['password'])
        response = self.client.get('/reset_password/' + token)
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            self.assertFalse(session.get('_flashes'))

    def test_password_reset_validates_confirmation_and_invalidates_used_token(self):
        token = application.email_service.generate_token(self.user['email'], self.user['password'])
        path = '/reset_password/' + token
        self.assertEqual(self.client.post(path, data={'password': 'NewPassword123', 'confirm-password': 'Different'}).status_code, 400)
        self.assertEqual(self.client.post(path, data={'password': 'NewPassword123', 'confirm-password': 'NewPassword123'}).status_code, 302)
        self.assertTrue(check_password_hash(self.db.users.find_one({'_id': self.user['_id']})['password'], 'NewPassword123'))
        self.assertEqual(self.client.get(path).status_code, 302)

    def test_optional_asset_fields_can_be_omitted(self):
        response = self.client.post('/save_asset', data={'asset-tag': 'MinimalAsset', 'category': 'Computers'})
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.db[self.company].find_one({'asset_tag': 'MinimalAsset', 'asset': True}))

    def test_invalid_asset_cost_is_rejected(self):
        for cost in ['not money', '-10', 'NaN', 'Infinity']:
            with self.subTest(cost=cost):
                self.assertEqual(self.client.post('/save_asset', data=self.asset_form(**{'purchase-cost': cost})).status_code, 400)
        self.assertEqual(self.db[self.company].count_documents({'asset': True}), 0)

    def test_category_names_with_regex_characters_detect_duplicates(self):
        self.db[self.company].insert_one({'category': True, 'name': 'C++'})
        self.client.post('/save_category', data={'category-name': 'C++', 'category-type': ''})
        self.assertEqual(self.db[self.company].count_documents({'category': True, 'name': 'C++'}), 1)

    def test_category_and_location_renames_update_asset_references(self):
        asset = self.asset()
        category_id = self.db[self.company].insert_one({'category': True, 'name': 'Computers'}).inserted_id
        location_id = self.db[self.company].insert_one({'location': True, 'location_tag': 'Office'}).inserted_id
        self.client.post('/save_category', data={'category_id': str(category_id), 'category-name': 'Hardware', 'category-type': ''})
        self.client.post('/save-location', data={'location_id': str(location_id), 'location-tag': 'NewOffice'})
        updated = self.db[self.company].find_one({'_id': asset['_id']})
        self.assertEqual(updated['category'], 'Hardware')
        self.assertEqual(updated['location'], 'NewOffice')

    def test_images_are_accessible_for_underscore_company(self):
        response = self.client.post('/save_asset', data={**self.asset_form(), 'image': (io.BytesIO(b'fake-image'), 'asset.png', 'image/png')})
        self.assertEqual(response.status_code, 302)
        asset = self.db[self.company].find_one({'asset': True})
        self.assertIsNotNone(asset)
        image = self.client.get('/image/' + str(asset['image_id']))
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.data, b'fake-image')

    def test_deleting_an_asset_removes_its_unused_image(self):
        self.client.post('/save_asset', data={**self.asset_form(), 'image': (io.BytesIO(b'fake-image'), 'asset.png', 'image/png')})
        asset = self.db[self.company].find_one({'asset': True})
        self.client.post('/delete_asset/' + str(asset['_id']))
        self.assertFalse(application.fs.exists(asset['image_id']))

    def test_uploads_cannot_be_served_as_active_html(self):
        response = self.client.post('/save_asset', data={**self.asset_form(), 'image': (io.BytesIO(b'<script>alert(1)</script>'), 'asset.html', 'text/html')})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db[self.company].count_documents({'asset': True}), 0)

    def test_in_use_category_and_location_are_preserved_on_delete(self):
        self.asset()
        for kind, name in [('category', 'Computers'), ('location', 'Office')]:
            field = 'name' if kind == 'category' else 'location_tag'
            object_id = self.db[self.company].insert_one({kind: True, field: name}).inserted_id
            self.client.post('/delete_' + kind + '/' + str(object_id))
            self.assertIsNotNone(self.db[self.company].find_one({'_id': object_id}))

    def test_edit_form_preserves_notes_and_purchase_date(self):
        asset = self.asset(notes='Original notes', purchase_date='2026-01-12')
        response = self.client.get('/asset-properties?asset_id=' + str(asset['_id']))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'rows="4">Original notes</textarea>', response.data)
        self.assertIn(b'name="purchase-date" value="2026-01-12"', response.data)

    def test_modal_save_updates_parent_without_discarding_asset_form(self):
        response = self.client.post('/save_category?modal=true', data={'category-name': 'NewCategory', 'category-type': 'Hardware'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'postMessage', response.data)
        self.assertNotIn(b'location.reload', response.data)
        self.assertIn(b'NewCategory', response.data)

    def test_valid_signup_preserves_company_collection_and_normalizes_email(self):
        response = self.client.post('/sign-up', data={'first-name': 'New', 'last-name': 'User', 'company': 'New_Company', 'email': 'NEW@EXAMPLE.INVALID', 'password': 'Password123', 'confirm-password': 'Password123'})
        self.assertEqual(response.status_code, 302)
        user = self.db.users.find_one({'email': 'new@example.invalid'})
        self.assertEqual(user['company'], 'New_Company')
        self.assertTrue(self.db['New_Company'].find_one({'user_id': user['_id']}))

    def test_heroku_requires_a_stable_secret_key(self):
        environment = os.environ.copy()
        environment['DYNO'] = 'web.1'
        environment.pop('SECRET_KEY', None)
        result = subprocess.run([sys.executable, '-c', 'import app'], env=environment, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Set SECRET_KEY in Heroku Config Vars', result.stderr)


if __name__ == '__main__':
    unittest.main()
