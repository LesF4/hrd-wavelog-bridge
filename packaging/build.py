"""Construit HRDtoWavelog pour Windows.

    python packaging/build.py               -> packaging/dist/HRDtoWavelog/ (dossier, pour l'installeur)
    python packaging/build.py --portable    -> + packaging/dist/HRDtoWavelog-portable.exe (un seul fichier)
    python packaging/build.py --installer   -> + packaging/dist/HRDtoWavelog-Setup-<version>.exe (Inno Setup 6)

Prérequis : pip install pyinstaller pystray pillow  (+ Inno Setup 6 pour --installer)
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(HERE, "dist")
WORK = os.path.join(HERE, "build")
sys.path.insert(0, ROOT)


def make_icon():
    from hrdwl.app import make_icon_image
    path = os.path.join(HERE, "icon.ico")
    make_icon_image(256).save(path, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    return path


def pyinstaller(icon, onefile, name):
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
           "--onefile" if onefile else "--onedir", "--name", name, "--icon", icon,
           "--distpath", DIST, "--workpath", WORK, "--specpath", WORK,
           os.path.join(ROOT, "HRDtoWavelog.pyw")]
    subprocess.run(cmd, check=True, cwd=ROOT)


def find_iscc():
    for path in (shutil.which("iscc"),
                 r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                 r"C:\Program Files\Inno Setup 6\ISCC.exe",
                 os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")):
        if path and os.path.exists(path):
            return path
    sys.exit("Inno Setup 6 introuvable (https://jrsoftware.org/isdl.php).")


def main():
    from hrdwl.core import APP_VERSION
    icon = make_icon()
    pyinstaller(icon, onefile=False, name="HRDtoWavelog")
    if "--portable" in sys.argv:
        pyinstaller(icon, onefile=True, name="HRDtoWavelog-portable")
    if "--installer" in sys.argv:
        subprocess.run([find_iscc(), "/DAppVersion=" + APP_VERSION, os.path.join(HERE, "installer.iss")],
                       check=True)
    print("\nTerminé :", DIST)


if __name__ == "__main__":
    main()
