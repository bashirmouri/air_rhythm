# PyInstaller recipe for the standalone game. Don't run this directly: use
#     python tools/build.py
# which first prepares build/bundle (pre-generated audio/beatmaps, the hand model,
# Windows version info) and afterwards adds the license files and the zip.
import os

from PyInstaller.utils.hooks import collect_all

root = os.path.dirname(SPECPATH)                 # the project folder (this file is in packaging/)
bundle = os.path.join(root, "build", "bundle")

datas = [
    (os.path.join(bundle, "pregenerated"), "pregenerated"),   # copied to the data folder on first start
    (os.path.join(bundle, "models"), "models"),               # hand model, used in place (no download)
    (os.path.join(root, "src", "air_rhythm", "resources"), os.path.join("air_rhythm", "resources")),  # icon
]
binaries, hiddenimports = [], []
# MediaPipe loads its native library and graph/data files at runtime, which PyInstaller
# can't see by following imports: take the whole package.
d, b, h = collect_all("mediapipe")
datas += d
binaries += b
hiddenimports += h

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    pathex=[os.path.join(root, "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "PyInstaller", "pytest"],
)
# OpenCV's FFmpeg plugin only decodes video files/streams. Webcams use Windows' Media
# Foundation backend, so leave out the 30 MB DLL.
a.binaries = [b for b in a.binaries if "opencv_videoio_ffmpeg" not in b[0].lower()]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,            # one-folder build: starts fast, and pygame's LGPL DLLs stay replaceable
    name="AirRhythm",
    console=False,                    # no terminal window; everything goes to the log file
    icon=os.path.join(root, "src", "air_rhythm", "resources", "icon.ico"),
    version=os.path.join(bundle, "version_info.txt"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AirRhythm", upx=False)
