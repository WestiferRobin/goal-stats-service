"""Source lifecycle failures use a recording disk-image provider, never real mounts."""

import hashlib
import json
import os
import plistlib
import subprocess
from types import SimpleNamespace

import pinned_source as source_mount
import pytest


@pytest.fixture
def mount_context(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    source = root / "results.csv"
    source.write_bytes(b"approved test source")
    monkeypatch.setattr(source_mount, "SOURCE", source)
    monkeypatch.setattr(source_mount, "SHA256", hashlib.sha256(source.read_bytes()).hexdigest())
    monkeypatch.setattr(source_mount.sys, "platform", "darwin")
    monkeypatch.setattr(source_mount, "validate_manifests", lambda: None)
    directory = root / "owned"
    context = SimpleNamespace(directory=directory, calls=[], images=[], fail=None)
    unrelated = {
        "image-path": "/unrelated/keep.dmg",
        "owner-uid": os.getuid(),
        "system-entities": [{"dev-entry": "/dev/disk7", "mount-point": "/Volumes/Keep"}],
    }
    context.images.append(unrelated)

    def hdi(*args):
        context.calls.append(tuple(map(str, args)))
        if args[0] == context.fail:
            raise subprocess.CalledProcessError(9, ["hdiutil", *args])
        if args[0] == "info":
            return plistlib.dumps({"images": context.images})
        if args[0] == "create":
            (directory / "source.dmg").write_bytes(b"image")
        if args[0] == "attach":
            (directory / "mount/results.csv").write_bytes(source.read_bytes())
            context.images.append(
                {
                    "image-path": str(directory / "source.dmg"),
                    "owner-uid": os.getuid(),
                    "writeable": False,
                    "system-entities": [
                        {"dev-entry": "/dev/disk8"},
                        {"dev-entry": "/dev/disk8s1", "mount-point": str(directory / "mount")},
                    ],
                }
            )
        if args[0] == "detach":
            assert args[1] == "/dev/disk8", "Must never detach unrelated mounts"
            context.images[:] = [unrelated]
        return b""

    monkeypatch.setattr(source_mount, "hdi", hdi)
    monkeypatch.setattr(source_mount.os, "statvfs", lambda _: SimpleNamespace(f_flag=os.ST_RDONLY))
    return context


def test_prepare_verify_cleanup_preserves_unrelated_images(mount_context):
    c = mount_context
    source_mount.prepare(c.directory, "token")
    assert source_mount.verify(c.directory, "token") == c.directory / "mount/results.csv"
    source_mount.cleanup(c.directory, "token")
    assert not c.directory.exists()
    assert [i["image-path"] for i in c.images] == ["/unrelated/keep.dmg"]
    assert sum(call[0] == "detach" for call in c.calls) == 1
    assert "-readonly" in next(call for call in c.calls if call[0] == "attach")


@pytest.mark.parametrize("failure", ["missing", "checksum", "manifest", "create", "attach"])
def test_preparation_failures_are_cleanable(mount_context, monkeypatch, failure):
    c = mount_context
    if failure == "missing":
        source_mount.SOURCE.unlink()
    elif failure == "checksum":
        source_mount.SOURCE.write_bytes(b"corrupt")
    elif failure == "manifest":

        def invalid():
            raise ValueError("Invalid manifest")

        monkeypatch.setattr(source_mount, "validate_manifests", invalid)
    else:
        c.fail = failure
    with pytest.raises((RuntimeError, ValueError, subprocess.CalledProcessError)):
        source_mount.prepare(c.directory, "token")
    source_mount.cleanup(c.directory, "token")
    assert not c.directory.exists()
    assert len(c.images) == 1


@pytest.mark.parametrize(
    "failure",
    ["token", "receipt", "owner", "foreign_mount", "writable", "filesystem", "checksum", "symlink"],
)
def test_source_verification_fails_closed(mount_context, monkeypatch, failure):
    c = mount_context
    source_mount.prepare(c.directory, "token")
    token = "wrong" if failure == "token" else "token"
    if failure == "receipt":
        file = c.directory / "receipt.json"
        data = json.loads(file.read_text())
        data["inode"] += 1
        file.write_text(json.dumps(data))
    elif failure == "owner":
        c.images[-1]["owner-uid"] += 1
    elif failure == "foreign_mount":
        c.images[-1]["image-path"] = "/unrelated/hostile.dmg"
    elif failure == "writable":
        c.images[-1]["writeable"] = True
    elif failure == "filesystem":
        monkeypatch.setattr(source_mount.os, "statvfs", lambda _: SimpleNamespace(f_flag=0))
    elif failure == "checksum":
        (c.directory / "mount/results.csv").write_bytes(b"corruption")
    elif failure == "symlink":
        (c.directory / "mount/results.csv").unlink()
        (c.directory / "mount/results.csv").symlink_to(source_mount.SOURCE)
    with pytest.raises(RuntimeError):
        source_mount.verify(c.directory, token)
    if failure in {"token", "receipt", "owner", "foreign_mount"}:
        with pytest.raises(RuntimeError):
            source_mount.cleanup(c.directory, token)
        assert not any(call[0] == "detach" for call in c.calls)
        assert c.directory.exists()


def test_detach_failure_retains_receipt_image_and_directory(mount_context):
    c = mount_context
    source_mount.prepare(c.directory, "token")
    c.fail = "detach"
    with pytest.raises(subprocess.CalledProcessError):
        source_mount.cleanup(c.directory, "token")
    assert (c.directory / "receipt.json").is_file()
    assert (c.directory / "source.dmg").is_file()
    assert len(c.images) == 2
    c.fail = None
    source_mount.cleanup(c.directory, "token")
    assert not c.directory.exists()


def test_partial_attach_discovered_without_success_receipt(mount_context, monkeypatch):
    c = mount_context
    original = source_mount.hdi

    def interrupted(*args):
        result = original(*args)
        if args[0] == "attach":
            raise KeyboardInterrupt()
        return result

    monkeypatch.setattr(source_mount, "hdi", interrupted)
    with pytest.raises(KeyboardInterrupt):
        source_mount.prepare(c.directory, "token")
    source_mount.cleanup(c.directory, "token")
    assert not c.directory.exists() and len(c.images) == 1


def test_existing_directory_never_reused(mount_context):
    c = mount_context
    c.directory.mkdir()
    (c.directory / "unrelated").write_text("keep")
    with pytest.raises(FileExistsError):
        source_mount.prepare(c.directory, "token")
    assert (c.directory / "unrelated").read_text() == "keep"
    assert not c.calls


def test_real_manifest_pin_and_missing_source_checks():
    source_mount.validate_manifests()


def test_changed_manifest_pin_rejected(monkeypatch):
    monkeypatch.setattr(
        source_mount,
        "load_manifest",
        lambda _: SimpleNamespace(sha256="wrong", upstream_revision=source_mount.REVISION),
    )
    with pytest.raises(RuntimeError, match="manifest"):
        source_mount.validate_manifests()
