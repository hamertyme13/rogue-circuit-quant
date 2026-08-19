import argparse
import os
import plistlib
import shutil
import stat
import struct
import subprocess
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Rogue Circuit Quant"
BUNDLE_ID = "com.roguecircuit.quant"
ICON_NAME = "RogueCircuitQuant"
PORT = 8765


def main():
    parser = argparse.ArgumentParser(
        description="Install the Rogue Circuit Quant macOS launcher."
    )
    parser.add_argument(
        "--target",
        default=str(Path.home() / "Desktop"),
        help="Directory where the .app bundle should be installed.",
    )
    args = parser.parse_args()

    target_dir = Path(args.target).expanduser()
    app_path = target_dir / f"{APP_NAME}.app"

    create_app_bundle(app_path)
    print(f"Installed {APP_NAME} at {app_path}")
    return 0


def create_app_bundle(app_path: Path):
    if app_path.exists():
        shutil.rmtree(app_path)

    contents = app_path / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)

    icon_path = resources / f"{ICON_NAME}.icns"
    create_icon(icon_path)
    write_info_plist(contents / "Info.plist")
    write_launcher(macos / "launcher")


def write_info_plist(path: Path):
    payload = {
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": "launcher",
        "CFBundleIconFile": ICON_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "10.13",
        "NSHighResolutionCapable": True,
        "LSUIElement": True,
    }

    with path.open("wb") as handle:
        plistlib.dump(payload, handle)


def write_launcher(path: Path):
    script = f"""#!/bin/zsh
set -u

ROOT="{ROOT}"
PORT="{PORT}"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/desktop-launcher.log"
mkdir -p "$LOG_DIR"

cd "$ROOT" || exit 1
echo "---- $(/bin/date) launcher start ----" >> "$LOG_FILE"

PYTHON="$ROOT/venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3)"
fi
echo "Using Python: $PYTHON" >> "$LOG_FILE"

server_is_stable() {{
  for _ in 1 2 3; do
    /usr/bin/curl -fsS "http://127.0.0.1:$PORT/api/state" >/dev/null 2>&1 || return 1
    /bin/sleep 0.35
  done
  return 0
}}

if server_is_stable; then
  echo "Server already running on $PORT" >> "$LOG_FILE"
  /usr/bin/open "http://127.0.0.1:$PORT"
  exit 0
fi

if /usr/bin/arch -arm64 "$PYTHON" -c "import ccxt, cryptography" >> "$LOG_FILE" 2>&1; then
  echo "Starting hidden app server with arm64 Python" >> "$LOG_FILE"
  /usr/bin/arch -arm64 "$PYTHON" "$ROOT/web_app.py" >> "$LOG_FILE" 2>&1 &
else
  echo "Starting hidden app server with default Python" >> "$LOG_FILE"
  "$PYTHON" "$ROOT/web_app.py" >> "$LOG_FILE" 2>&1 &
fi
SERVER_PID=$!

trap '/bin/kill "$SERVER_PID" >/dev/null 2>&1 || true' TERM INT EXIT

for _ in {{1..80}}; do
  if server_is_stable; then
    echo "Server is ready on $PORT" >> "$LOG_FILE"
    /usr/bin/open "http://127.0.0.1:$PORT"
    wait "$SERVER_PID"
    exit $?
  fi
  /bin/sleep 0.25
done

echo "Server did not respond before timeout" >> "$LOG_FILE"
/bin/kill "$SERVER_PID" >/dev/null 2>&1 || true
exit 1
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def create_icon(icon_path: Path):
    iconset = icon_path.with_suffix(".iconset")
    if iconset.exists():
        shutil.rmtree(iconset)

    iconset.mkdir(parents=True)
    base = icon_path.with_name(f"{ICON_NAME}-source.png")
    write_png(base, 1024)

    sizes = [
        (16, "icon_16x16.png", b"icp4"),
        (32, "icon_32x32.png", b"icp5"),
        (64, "icon_32x32@2x.png", b"icp6"),
        (128, "icon_128x128.png", b"ic07"),
        (256, "icon_256x256.png", b"ic08"),
        (512, "icon_512x512.png", b"ic09"),
        (1024, "icon_512x512@2x.png", b"ic10"),
    ]

    icon_entries = []

    for size, name, icon_type in sizes:
        output = iconset / name
        if size == 1024:
            shutil.copyfile(base, output)
        else:
            subprocess.run(
                [
                    "sips",
                    "-z",
                    str(size),
                    str(size),
                    str(base),
                    "--out",
                    str(output),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        icon_entries.append((icon_type, output.read_bytes()))

    write_icns(icon_path, icon_entries)
    shutil.rmtree(iconset)
    base.unlink(missing_ok=True)


def write_icns(
    icon_path: Path,
    entries: list[tuple[bytes, bytes]],
):

    chunks = []

    for icon_type, data in entries:
        chunks.append(
            icon_type
            + struct.pack(">I", len(data) + 8)
            + data
        )

    payload = b"".join(chunks)
    icon_path.write_bytes(
        b"icns"
        + struct.pack(">I", len(payload) + 8)
        + payload
    )


def write_png(path: Path, size: int):
    rows = []

    for y in range(size):
        row = bytearray()
        for x in range(size):
            row.extend(pixel(x, y, size))
        rows.append(b"\x00" + bytes(row))

    raw = b"".join(rows)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def pixel(x: int, y: int, size: int):
    center = (size - 1) / 2
    nx = (x - center) / center
    ny = (y - center) / center
    radius = (nx * nx + ny * ny) ** 0.5

    if radius > 0.96:
        return (0, 0, 0, 0)

    edge = 1.0 if radius < 0.91 else max(0.0, (0.96 - radius) / 0.05)
    scan = 0.04 if (y // 18) % 2 == 0 else 0.0
    vignette = max(0.0, 1 - radius * 0.72)
    r = int((5 + 35 * (1 - ny) + 95 * max(nx, 0)) * vignette)
    g = int((15 + 190 * (1 - radius) + 45 * max(-ny, 0) + scan * 255) * edge)
    b = int((28 + 210 * max(nx, 0) + 70 * (1 - radius)) * edge)
    a = int(255 * edge)

    if on_circuit_mark(x, y, size):
        return (57, 255, 136, a)

    if on_ring(radius):
        return (25, 230, 255, a)

    if on_accent_node(x, y, size):
        return (124, 60, 255, a)

    return (clamp(r), clamp(g), clamp(b), a)


def on_ring(radius: float) -> bool:
    return 0.70 <= radius <= 0.735 or 0.385 <= radius <= 0.405


def on_circuit_mark(x: int, y: int, size: int) -> bool:
    sx = x / size
    sy = y / size
    stroke = 0.025
    left = abs(sx - 0.36) < stroke and 0.28 < sy < 0.72
    top = abs(sy - 0.28) < stroke and 0.36 < sx < 0.57
    middle = abs(sy - 0.50) < stroke and 0.36 < sx < 0.56
    diagonal = abs((sy - 0.29) - (sx - 0.56) * 1.55) < stroke and 0.55 < sx < 0.70
    bottom = abs(sy - 0.72) < stroke and 0.40 < sx < 0.68
    right = abs(sx - 0.68) < stroke and 0.54 < sy < 0.72
    return left or top or middle or diagonal or bottom or right


def on_accent_node(x: int, y: int, size: int) -> bool:
    points = [
        (0.28, 0.28),
        (0.72, 0.32),
        (0.30, 0.74),
        (0.72, 0.72),
    ]
    sx = x / size
    sy = y / size

    return any(
        ((sx - px) ** 2 + (sy - py) ** 2) ** 0.5 < 0.035
        for px, py in points
    )


def chunk(kind: bytes, data: bytes):
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def clamp(value: int):
    return max(0, min(255, value))


if __name__ == "__main__":
    raise SystemExit(main())
