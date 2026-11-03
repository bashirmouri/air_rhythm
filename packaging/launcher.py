"""Entry point PyInstaller turns into AirRhythm.exe. Kept outside the package so the
packaged game starts the same way `python -m air_rhythm` does."""
from air_rhythm.app import main

main()
