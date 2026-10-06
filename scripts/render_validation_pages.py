"""Render representative HTML against a disposable local test database."""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
uri = os.environ.get("ASSETY_TEST_MONGO_URI", "mongodb://127.0.0.1:27019")
if urlsplit(uri).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Validation requires a local disposable MongoDB server.")
os.environ["ASSETY_TEST_MONGO_URI"] = uri

from test_app import AppRegressionTests, application  # noqa: E402


def main():
    """Write generated pages for the offline Nu HTML checker."""
    output = ROOT / ".local" / "validation"
    output.mkdir(parents=True, exist_ok=True)
    AppRegressionTests.setUpClass()
    case = AppRegressionTests()
    try:
        case.setUp()
        asset = case.asset(notes="Validation example", purchase_date="2026-10-06")
        category = case.db[case.company].find_one({"category": True})
        location = case.db[case.company].find_one({"location": True})
        token = application.email_service.generate_token(
            case.user["email"], case.user["password"]
        )
        pages = {
            "home": "/",
            "login": "/login",
            "sign-up": "/sign-up",
            "forgot-password": "/forgot-password",
            "reset-password": "/reset_password/" + token,
            "inventory": "/inventory",
            "dashboard": "/dashboard",
            "assets": "/assets",
            "categories": "/categories",
            "locations": "/locations",
            "reports": "/reports",
            "logs": "/logs",
            "settings": "/settings",
            "profile": "/profile",
            "new-asset": "/new-asset",
            "view-asset": "/asset/" + str(asset["_id"]),
            "edit-asset": "/asset-properties?asset_id=" + str(asset["_id"]),
            "new-category": "/new-category",
            "edit-category": "/category-properties?category_id=" + str(category["_id"]),
            "new-location": "/new-location",
            "edit-location": "/location-properties?location_id=" + str(location["_id"]),
            "category-modal": "/new-category?modal=true",
            "location-modal": "/new-location?modal=true",
            "logout": "/logout",
            "not-found": "/nonexistent-validation-page",
        }
        for name, path in pages.items():
            response = case.client.get(path)
            expected = 404 if name == "not-found" else 200
            if response.status_code != expected:
                raise RuntimeError(
                    f"{name}: expected {expected}, got {response.status_code}"
                )
            (output / f"{name}.html").write_bytes(response.data)
        for name, path, data in [
            ("asset-error", "/save_asset", case.asset_form(**{"purchase-cost": "-1"})),
            (
                "category-error",
                "/save_category?modal=true",
                {"category-name": "Computers", "category-type": "Draft"},
            ),
        ]:
            response = case.client.post(path, data=data)
            if response.status_code != 400:
                raise RuntimeError(f"{name}: expected validation error")
            (output / f"{name}.html").write_bytes(response.data)
        print(f"Rendered {len(pages) + 2} HTML pages to {output}")
    finally:
        AppRegressionTests.tearDownClass()


if __name__ == "__main__":
    main()
