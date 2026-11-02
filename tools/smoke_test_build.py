"""Starts the built game (dist/AirRhythm/AirRhythm.exe) headless with an empty data folder,
lets it run for a few seconds, and checks from its log that it worked:

- it ran as the packaged build and closed normally (exit code 0)
- nothing was downloaded or generated (bundled model and pre-generated files were used)
- no unexpected error
- MediaPipe's hand tracker loaded (the camera itself may be missing, e.g. on a build server)

    python tools/smoke_test_build.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "dist", "AirRhythm", "AirRhythm.exe" if sys.platform == "win32" else "AirRhythm")


def main():
    if not os.path.exists(EXE):
        sys.exit(f"No build at {EXE}: run tools/build.py first")
    data = tempfile.mkdtemp(prefix="air_rhythm_smoke_")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "VIRTUAL_ENV"))}
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                  if "python" not in p.lower())          # no Python to lean on
    env.update(AIR_RHYTHM_DATA_DIR=data, AIR_RHYTHM_QUIT_AFTER_S="10",
               SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    try:
        code = subprocess.run([EXE], env=env, cwd=data, timeout=120,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        log = open(os.path.join(data, "air_rhythm.log"), encoding="utf-8").read()
    finally:
        shutil.rmtree(data, ignore_errors=True)

    checks = {
        "exit code 0": code == 0,
        "ran as the packaged build": "(packaged build)" in log,
        "closed normally": "Air Rhythm closed" in log,
        "nothing downloaded": "Downloading" not in log,
        "nothing generated (pre-generated files used)": "Generating" not in log,
        "no unexpected error": "Unexpected error" not in log and "Startup failed" not in log,
        "hand tracker loaded (camera opened, or only the camera is missing)":
            "Camera 0 opened" in log or "Could not open the webcam" in log,
    }
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not all(checks.values()):
        print("\n--- log ---\n" + log)
        sys.exit(1)
    print("Packaged game works.")


if __name__ == "__main__":
    main()
