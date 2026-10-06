"""Validate generated HTML and project CSS with the official offline Nu checker."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / ".local" / "validator" / "vnu-runtime-image" / "bin" / "java.exe"


def main():
    """Keep validator output locally and fail when any errors are reported."""
    if not CHECKER.exists():
        raise SystemExit(
            "Install the portable Nu checker as described in docs/testing.md."
        )
    errors = 0
    for name, args in [
        ("html", [str(ROOT / ".local" / "validation")]),
        (
            "css",
            [
                "--css",
                str(ROOT / "static/css/styles.css"),
                str(ROOT / "static/css/responsive.css"),
            ],
        ),
    ]:
        result = subprocess.run(
            [
                str(CHECKER),
                "-m",
                "vnu/nu.validator.client.SimpleCommandLineValidator",
                "--format",
                "json",
                *args,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        report = json.loads(result.stderr or result.stdout)
        (ROOT / ".local" / f"{name}-validation.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        failures = [m for m in report["messages"] if m["type"] == "error"]
        warnings = [m for m in report["messages"] if m["type"] != "error"]
        errors += len(failures)
        print(
            f"{name.upper()}: {len(failures)} errors, {len(warnings)} warnings; {report['version']}"
        )
        for message in failures:
            print(message.get("url", ""), message["message"])
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
