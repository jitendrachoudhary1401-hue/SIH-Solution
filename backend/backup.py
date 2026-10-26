"""Snapshot a stopped local SQLite experiment and private evidence into a ZIP.

For PostgreSQL use pg_dump and the private runtime volume together (README).
Restore writes only to a new directory; it never overwrites an existing database.
"""
import argparse
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path


def backup(database, documents, destination):
    database, documents, destination = Path(database), Path(documents), Path(destination)
    if destination.exists():
        raise ValueError("Backup destination already exists; choose a new filename")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="onecase-backup-") as temp:
        snapshot = Path(temp) / "onecase.db"
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(snapshot)) as target:
            source.backup(target)
        with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "onecase.db")
            checksums = {"onecase.db": hashlib.sha256(snapshot.read_bytes()).hexdigest()}
            for path in documents.iterdir():
                if path.is_file():
                    name = "documents/" + path.name
                    archive.write(path, name)
                    checksums[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            archive.writestr("manifest.json", json.dumps({"version": 1, "checksums": checksums}, indent=2))
    return destination


def restore(archive_path, target):
    target = Path(target).resolve()
    if target.exists():
        raise ValueError("Restore destination must not exist")
    with zipfile.ZipFile(archive_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if "onecase.db" not in manifest["checksums"]:
            raise ValueError("Database missing from backup")
        contents = {}
        for name, checksum in manifest["checksums"].items():
            path = (target / name).resolve()
            if not path.is_relative_to(target) or name not in archive.namelist():
                raise ValueError("Unsafe backup path")
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError("Backup checksum mismatch")
            contents[path] = data
        for path, data in contents.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    with closing(sqlite3.connect(target / "onecase.db")) as connection:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Restored database integrity check failed")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)
    save = sub.add_parser("save")
    save.add_argument("--database", default=".runtime/onecase.db")
    save.add_argument("--documents", default=".runtime/documents")
    save.add_argument("--output", required=True)
    load = sub.add_parser("restore")
    load.add_argument("archive")
    load.add_argument("--target", required=True)
    args = parser.parse_args()
    print(backup(args.database, args.documents, args.output) if args.operation == "save" else restore(args.archive, args.target))
