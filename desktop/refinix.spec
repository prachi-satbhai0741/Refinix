# PyInstaller spec for the Windows and Linux lanes. Run by desktop/build.py:
#     pyinstaller --noconfirm --distpath <dist> --workpath <work> desktop/refinix.spec
# with REFINIX_STAGED_SOURCES (the staged application sources) and
# REFINIX_BUILD_IDENTITY (the embedded build identity) in the environment.
#
# The application boundary is desktop/packaging_plan.py, the same one the macOS
# py2app build uses: only staged application modules, the shipped frontend and
# the build identity are included. The engine is placed afterwards by build.py.
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

DESKTOP = Path(SPECPATH).resolve()                     # noqa: F821 - PyInstaller global
REPO = DESKTOP.parent
STAGED = Path(os.environ["REFINIX_STAGED_SOURCES"]).resolve()
IDENTITY = Path(os.environ["REFINIX_BUILD_IDENTITY"]).resolve()
sys.path.insert(0, str(STAGED))
sys.path.insert(0, str(DESKTOP))
import packaging_plan  # noqa: E402

datas = [(source, destination)
         for destination, sources in packaging_plan.frontend_data_files()
         for source in sources]
datas.append((str(IDENTITY), "."))
# The update trust root and channel feed, when this build has them.
for _name in ("REFINIX_UPDATE_ROOT", "REFINIX_UPDATE_FEED"):
    if os.environ.get(_name):
        datas.append((str(Path(os.environ[_name]).resolve()), "."))
datas += collect_data_files("webview")
datas += collect_data_files("pypdfium2_raw")
binaries = collect_dynamic_libs("pypdfium2_raw")

hiddenimports = (collect_submodules("backend.coordinator")
                 + collect_submodules("backend.contracts")
                 + collect_submodules("desktop")
                 + ["psutil", "tuf.ngclient", "tuf.api.metadata", "securesystemslib",
                 "securesystemslib._vendor.ed25519.ed25519", "urllib3"])
hiddenimports = [name for name in hiddenimports
                 if not name.rsplit(".", 1)[-1].startswith(
                     packaging_plan.EXCLUDED_MODULE_PREFIXES)]

if sys.platform == "win32":
    platform, icon = "windows", str(packaging_plan.icon_for("windows"))
else:
    platform, icon = "linux", None

a = Analysis(                                            # noqa: F821
    [str(STAGED / "desktop" / "refinix.py")],
    pathex=[str(STAGED)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "unittest", "pydoc_data", "test", "backend.worker",
              "PyInstaller", "pip", "setuptools"],
    noarchive=False,
)
if platform == "linux":
    # WebKitGTK starts helper processes from the system's own library folder,
    # so the application uses the distribution's GTK and WebKitGTK rather than
    # private copies whose helpers it could not find. The window toolkit
    # preflight explains a missing system package instead of failing silently.
    system_toolkit = ("libwebkit2gtk", "libjavascriptcoregtk", "libgtk-3",
                      "libgdk-3", "libsoup")
    a.binaries = [entry for entry in a.binaries
                  if not Path(entry[0]).name.startswith(system_toolkit)]
pyz = PYZ(a.pure)                                        # noqa: F821
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,    # noqa: F821
          name="Refinix", console=False, icon=icon,
          disable_windowed_traceback=True)
coll = COLLECT(exe, a.binaries, a.datas, name="Refinix")  # noqa: F821
