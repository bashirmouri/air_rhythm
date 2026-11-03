"""Writes the GitHub release notes for the current version: download instructions, that
version's section of CHANGELOG.md, the privacy note and the zip's SHA-256.

    python tools/release_notes.py dist/AirRhythm-0.2.0-windows-x64.zip > notes.md

Fails if CHANGELOG.md has no "## [<version>]" section, so a release can't go out without notes.
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from air_rhythm import __version__  # noqa: E402

REPO = "https://github.com/bashirmouri/air_rhythm"


def changelog_section(version):
    text = open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read()
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S)
    if not m or not m.group(1).strip():
        sys.exit(f"CHANGELOG.md has no section for [{version}]. Add one before releasing.")
    return m.group(1).strip()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    zip_path = sys.argv[1]
    sha = hashlib.sha256(open(zip_path, "rb").read()).hexdigest()
    name = os.path.basename(zip_path)
    print(f"""## Download (Windows 10/11, 64-bit)
1. Download **{name}** below.
2. Unzip it anywhere and run `AirRhythm\\AirRhythm.exe`. No Python or install needed, and it works offline.
3. Windows may show a SmartScreen warning because the game isn't code-signed:
   click **More info → Run anyway**.

Updating from an older version: replace the old folder. Your settings and calibration are kept
(they're stored in `%LOCALAPPDATA%\\AirRhythm`, not in the game folder).

## What's new in {__version__}
{changelog_section(__version__)}

Full history: [CHANGELOG.md]({REPO}/blob/v{__version__}/CHANGELOG.md)

**Privacy:** the camera image is processed on your computer only. It is never saved or sent anywhere.

SHA-256 of the zip: `{sha}`""")


if __name__ == "__main__":
    main()
