"""Builds the standalone game: dist/AirRhythm/ (run AirRhythm.exe) and a zip of it.

    python -m venv .venv
    .venv\\Scripts\\python -m pip install -r requirements-dev.txt
    .venv\\Scripts\\python tools/build.py

Steps: check pinned versions -> pre-generate audio and beatmaps -> bundle the verified
hand model -> Windows version info -> PyInstaller -> license files -> zip.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile
from importlib import metadata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
BUNDLE = os.path.join(BUILD, "bundle")
DIST = os.path.join(ROOT, "dist")
APP = os.path.join(DIST, "AirRhythm")
SRC = os.path.join(ROOT, "src")                  # the air_rhythm package
sys.path.insert(0, SRC)
from air_rhythm import __version__  # noqa: E402

# Installed only to build, not shipped (their licenses don't need to go in the build)
BUILD_ONLY = {"air-rhythm", "pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile",
              "pywin32-ctypes", "setuptools", "pip"}


def step(msg):
    print(f"\n== {msg}", flush=True)


def run(args, **env):
    # PYTHONPATH: the steps below import air_rhythm, installed with `pip install -e .` or not
    path = os.pathsep.join(p for p in (SRC, os.environ.get("PYTHONPATH")) if p)
    subprocess.run(args, cwd=ROOT, check=True, env={**os.environ, "PYTHONPATH": path, **env})


def check_versions():
    """The build must use exactly the versions in requirements.txt (the tested ones)."""
    step("Checking pinned versions")
    bad = []
    for line in open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8"):
        m = re.match(r"\s*([A-Za-z0-9_.-]+)==([^\s#]+)", line)
        if not m:
            continue
        name, want = m.groups()
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            have = "not installed"
        print(f"   {name:24} {have:12} {'ok' if have == want else 'expected ' + want}")
        if have != want:
            bad.append(name)
    if bad:
        sys.exit("Install the pinned versions first: pip install -r requirements-dev.txt")
    if "opencv-python" in {d.metadata["Name"].lower() for d in metadata.distributions()}:
        sys.exit("Both opencv-python and opencv-contrib-python are installed (they clash). "
                 "Build from a fresh venv.")


def pregenerate():
    step("Pre-generating songs, beatmaps and menu music")
    out = os.path.join(BUNDLE, "pregenerated")
    run([sys.executable, "-m", "air_rhythm.content.map_gen"], AIR_RHYTHM_DATA_DIR=out)
    for junk in ("settings.json", "air_rhythm.log"):          # only game files belong here
        if os.path.exists(os.path.join(out, junk)):
            os.remove(os.path.join(out, junk))


def bundle_model():
    step("Bundling the hand model")
    from air_rhythm.controls import hand_tracker
    # The game's own download code fetches it (pinned URL + checksum). build/model_download
    # is kept between builds, so this only downloads the first time.
    cache = os.path.join(BUILD, "model_download")
    run([sys.executable, "-c",
         "from air_rhythm.controls import hand_tracker; print(hand_tracker.ensure_model())"],
        AIR_RHYTHM_DATA_DIR=cache)
    src = os.path.join(cache, "models", "hand_landmarker.task")
    digest = hashlib.sha256(open(src, "rb").read()).hexdigest()
    if digest != hand_tracker.MODEL_SHA256:
        sys.exit(f"Hand model {src} doesn't match the expected checksum")
    os.makedirs(os.path.join(BUNDLE, "models"))
    shutil.copy2(src, os.path.join(BUNDLE, "models", "hand_landmarker.task"))
    print("   verified", src)


def version_info():
    """Shown in Windows Explorer under the .exe's Properties > Details."""
    nums = tuple(int(x) for x in re.findall(r"\d+", __version__)[:3]) + (0,)
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Bashir Mouri'),
    StringStruct('FileDescription', 'Air Rhythm'),
    StringStruct('FileVersion', '{__version__}'),
    StringStruct('InternalName', 'AirRhythm'),
    StringStruct('LegalCopyright', 'Copyright (c) 2026 Bashir Mouri. MIT License.'),
    StringStruct('OriginalFilename', 'AirRhythm.exe'),
    StringStruct('ProductName', 'Air Rhythm'),
    StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"""
    open(os.path.join(BUNDLE, "version_info.txt"), "w", encoding="utf-8").write(text)


def pyinstaller():
    step("Running PyInstaller (a few minutes)")
    if not os.path.exists(os.path.join(SRC, "air_rhythm", "resources", "icon.ico")):
        run([sys.executable, os.path.join("tools", "make_icon.py")])
    run([sys.executable, "-m", "PyInstaller", os.path.join("packaging", "air_rhythm.spec"),
         "--noconfirm", "--clean",
         "--distpath", DIST, "--workpath", os.path.join(BUILD, "pyinstaller")])


def license_files():
    """The game's own license and notices next to the .exe, plus each bundled package's
    license/NOTICE files (Apache 2.0 and LGPL require shipping them)."""
    step("Adding license files")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "CHANGELOG.md"):
        shutil.copy2(os.path.join(ROOT, name), APP)
    out = os.path.join(APP, "licenses")
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if name.lower() in BUILD_ONLY:
            continue
        for f in dist.files or []:
            fname = os.path.basename(str(f)).upper()
            if fname.startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")):
                dst = os.path.join(out, name, os.path.basename(str(f)))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(f.locate(), dst)
    print("   packages with license files:", len(os.listdir(out)))


def make_zip():
    plat = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    path = os.path.join(DIST, f"AirRhythm-{__version__}-{plat}-x64.zip")
    step(f"Zipping {os.path.basename(path)}")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for folder, _, files in os.walk(APP):
            for f in files:
                full = os.path.join(folder, f)
                z.write(full, os.path.relpath(full, DIST))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(APP) for f in fs)
    print(f"   folder {size / 1e6:.0f} MB, zip {os.path.getsize(path) / 1e6:.0f} MB")
    return path


def main():
    print(f"Building Air Rhythm {__version__} with Python {sys.version.split()[0]}")
    check_versions()
    shutil.rmtree(BUNDLE, ignore_errors=True)
    shutil.rmtree(APP, ignore_errors=True)
    os.makedirs(BUNDLE)
    pregenerate()
    bundle_model()
    version_info()
    pyinstaller()
    license_files()
    path = make_zip()
    print(f"\nDone: {APP}\\AirRhythm.exe\n      {path}")


if __name__ == "__main__":
    main()
