import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    pyinstaller = shutil.which("pyinstaller")

    if pyinstaller is None:
        print(
            "PyInstaller is not installed. Install it with "
            "`python3 -m pip install pyinstaller` and rerun this script."
        )
        return 1

    command = [
        pyinstaller,
        "--name",
        "Rogue Circuit Quant",
        "--windowed",
        "--onefile",
        "desktop_app.py",
    ]

    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
