#!/usr/bin/env python3
"""Download the metrics database (or packaged ZIP) for a hosted deployment."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_NAME = "branded_food_filter_metrics.sqlite3"
DB_PATH = BASE_DIR / DB_NAME
SQLITE_HEADER = b"SQLite format 3\x00"
CHUNK_SIZE = 8 * 1024 * 1024


def copy_stream(source, destination: Path) -> None:
    with destination.open("wb") as output:
        shutil.copyfileobj(source, output, length=CHUNK_SIZE)


def main() -> int:
    url = os.environ.get("METRICS_DB_URL", "").strip()
    if not url.startswith("https://"):
        print("Set METRICS_DB_URL to an HTTPS link to the database or package ZIP.", file=sys.stderr)
        return 2

    downloaded = None
    unpacked = None
    try:
        with tempfile.NamedTemporaryFile(dir=BASE_DIR, suffix=".download", delete=False) as temp:
            downloaded = Path(temp.name)
        request = urllib.request.Request(url, headers={"User-Agent": "branded-food-filter/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response:
            copy_stream(response, downloaded)

        with downloaded.open("rb") as source:
            header = source.read(len(SQLITE_HEADER))
        if header == SQLITE_HEADER:
            downloaded.replace(DB_PATH)
            downloaded = None
        elif zipfile.is_zipfile(downloaded):
            with zipfile.ZipFile(downloaded) as archive:
                try:
                    info = archive.getinfo(DB_NAME)
                except KeyError as exc:
                    raise ValueError(f"The ZIP does not contain {DB_NAME} at its top level.") from exc
                with tempfile.NamedTemporaryFile(dir=BASE_DIR, suffix=".sqlite-download", delete=False) as temp:
                    unpacked = Path(temp.name)
                with archive.open(info) as source:
                    copy_stream(source, unpacked)
            with unpacked.open("rb") as source:
                if source.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                    raise ValueError("The extracted file is not a SQLite database.")
            unpacked.replace(DB_PATH)
            unpacked = None
        else:
            raise ValueError("The download is neither a SQLite database nor a ZIP package.")

        print(f"Database ready: {DB_PATH.name} ({DB_PATH.stat().st_size:,} bytes)")
        return 0
    except Exception as exc:
        print(f"Could not prepare the metrics database: {exc}", file=sys.stderr)
        return 1
    finally:
        for path in (downloaded, unpacked):
            if path is not None:
                path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
