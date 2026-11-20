import shutil

import pytest

from football import bootstrap_enrichment as source


def test_approved_packaged_evidence_is_complete():
    manifest, package = source.verify_evidence()
    assert len(manifest["releases"]) == len(package) == 96
    assert sum(len(rows) for _, rows in package) == 16525


@pytest.mark.parametrize("damage", ["missing", "manifest", "index", "response"])
def test_missing_or_modified_evidence_rejected(tmp_path, damage):
    if damage == "missing":
        with pytest.raises(FileNotFoundError):
            source.verify_evidence(tmp_path)
        return
    shutil.copytree(source.PACKAGE, tmp_path, dirs_exist_ok=True)
    manifest, _ = source.verify_evidence(tmp_path)
    name = {
        "manifest": "manifest.json",
        "index": "index.html",
        "response": manifest["releases"][0]["id"] + ".json",
    }[damage]
    with (tmp_path / name).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="checksum|provenance"):
        source.verify_evidence(tmp_path)


def test_wrong_approved_inventory_rejected(monkeypatch):
    monkeypatch.setattr(source.enrichment, "load_package", lambda directory: ({}, []))
    with pytest.raises(ValueError, match="inventory"):
        source.verify_evidence()
