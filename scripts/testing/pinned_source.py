"""Invocation-owned macOS read-only source image for canonical certification."""

import hashlib
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from football.historical_dataset import APPROVED_DATASETS, load_manifest

ROOT = Path(__file__).resolve().parents[2]
HDIUTIL = "/usr/bin/hdiutil"
REVISION = "1855e313ae8bcd0330426e62c8e4cf15ce45077c"
SHA256 = "de1dc4322c2d686981da32f577bfb5ddce4d3f71dea8023e05acfba7250743b0"
SOURCE = ROOT / "data/raw/martj42-womens-results" / REVISION / "results.csv"


def hdi(*args):
    return subprocess.run(
        [HDIUTIL, *map(str, args)], check=True, capture_output=True, timeout=60
    ).stdout


def images():
    return plistlib.loads(hdi("info", "-plist"))["images"]


def checksum(source):
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError("Approved source missing or checksum mismatch")


def validate_manifests():
    for dataset in APPROVED_DATASETS:
        manifest = load_manifest(dataset)
        if manifest.sha256 != SHA256 or manifest.upstream_revision != REVISION:
            raise RuntimeError("Historical manifest does not match the approved source")


def receipt(directory, token):
    info = directory.lstat()
    if (
        directory != directory.resolve()
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise RuntimeError("Source directory ownership mismatch")
    file = directory / "receipt.json"
    if file.is_symlink():
        raise RuntimeError("Source receipt must not be a symlink")
    data = json.loads(file.read_text())
    if data != {
        "directory": str(directory),
        "device": info.st_dev,
        "inode": info.st_ino,
        "uid": os.getuid(),
        "token": token,
    }:
        raise RuntimeError("Source receipt ownership mismatch")
    return data


def owned_image(directory):
    image = directory / "source.dmg"
    if image.is_symlink():
        raise RuntimeError("Source image must not be a symlink")
    inventory = images()
    matches = [i for i in inventory if i.get("image-path") == str(image)]
    # A foreign image occupying our mountpoint must never be detached or removed.
    for item in inventory:
        for entity in item.get("system-entities", []):
            if entity.get("mount-point") == str(directory / "mount") and item not in matches:
                raise RuntimeError("Source mount ownership mismatch")
    if len(matches) > 1:
        raise RuntimeError("Ambiguous source image ownership")
    if not matches:
        if os.path.ismount(directory / "mount"):
            raise RuntimeError("Unidentified source mount")
        return None
    item = matches[0]
    if item.get("owner-uid") != os.getuid() or not image.is_file():
        raise RuntimeError("Source image ownership mismatch")
    if image.stat().st_uid != os.getuid():
        raise RuntimeError("Source image file ownership mismatch")
    for entity in item.get("system-entities", []):
        if entity.get("mount-point") not in (None, str(directory / "mount")):
            raise RuntimeError("Source image mounted at unexpected location")
    return item


def verify(directory, token):
    receipt(directory, token)
    item = owned_image(directory)
    source = directory / "mount/results.csv"
    if item is None or item.get("writeable") is not False:
        raise RuntimeError("Source image is not read-only")
    if not any(e.get("mount-point") == str(source.parent) for e in item.get("system-entities", [])):
        raise RuntimeError("Source mount unavailable")
    if source != source.resolve() or not os.statvfs(source).f_flag & os.ST_RDONLY:
        raise RuntimeError("Source path must be canonical on a read-only filesystem")
    checksum(source)
    return source


def prepare(directory, token):
    if sys.platform != "darwin":
        raise RuntimeError("Certification requires supported macOS read-only source mounting")
    validate_manifests()
    checksum(SOURCE)
    # The caller owns the parent session. A preexisting child is never reused.
    directory.mkdir(mode=0o700)
    info = directory.stat()
    (directory / "receipt.json").write_text(
        json.dumps(
            dict(
                directory=str(directory),
                device=info.st_dev,
                inode=info.st_ino,
                uid=os.getuid(),
                token=token,
            )
        )
    )
    (directory / "input").mkdir()
    (directory / "mount").mkdir()
    shutil.copyfile(SOURCE, directory / "input/results.csv")
    checksum(directory / "input/results.csv")
    hdi(
        "create",
        "-srcfolder",
        directory / "input",
        "-format",
        "UDRO",
        "-fs",
        "HFS+",
        "-volname",
        "GoalStatsSource",
        directory / "source.dmg",
    )
    hdi(
        "attach",
        "-readonly",
        "-nobrowse",
        "-mountpoint",
        directory / "mount",
        "-plist",
        directory / "source.dmg",
    )
    verify(directory, token)
    print("Pinned source mounted read-only; approved SHA-256 verified", flush=True)


def cleanup(directory, token):
    if not directory.exists() and not directory.is_symlink():
        return
    receipt(directory, token)
    item = owned_image(directory)
    if item is not None:
        devices = [e.get("dev-entry", "") for e in item.get("system-entities", [])]
        whole = [d for d in devices if re.fullmatch(r"/dev/disk[0-9]+", d)]
        if len(whole) != 1:
            raise RuntimeError("Source device ownership is ambiguous")
        hdi("detach", whole[0])
    if owned_image(directory) is not None:
        raise RuntimeError("Owned source mount remains attached")
    # Never traverse nested mounts or substituted links during recursive removal.
    for path in directory.rglob("*"):
        if path.is_symlink() or os.path.ismount(path):
            raise RuntimeError("Unexpected link or mount in source artifacts")
    shutil.rmtree(directory)
    if directory.exists():
        raise RuntimeError("Owned source artifacts remain")


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in {"prepare", "verify", "cleanup"}:
        raise RuntimeError("Expected source lifecycle operation, directory and session token")
    operation, path, token = sys.argv[1:]
    directory = Path(path)
    if not directory.is_absolute() or directory != directory.resolve():
        raise RuntimeError("Source directory must be canonical")
    globals()[operation](directory, token)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.exit(f"Pinned-source lifecycle failed ({type(error).__name__}): {error}")
