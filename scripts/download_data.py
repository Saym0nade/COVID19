from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_data import (
    CATALOG_DATA_URLS,
    CATALOG_DIR,
    CATALOG_METADATA_URLS,
    LEGACY_SOURCES,
    RAW_DIR,
)


def download(url: str, destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        print(f"skip {destination} ({destination.stat().st_size} bytes)")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"download {destination}")
    urllib.request.urlretrieve(url, destination)
    print(f"done {destination} ({destination.stat().st_size} bytes)")


def download_group(sources: dict[str, str], destination_dir: Path, force: bool) -> None:
    for name, url in sources.items():
        download(url, destination_dir / name, force)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download OWID COVID-19 datasets")
    parser.add_argument("--force", action="store_true", help="redownload existing files")
    parser.add_argument("--legacy-only", action="store_true", help="download only legacy GitHub files")
    parser.add_argument("--catalog-only", action="store_true", help="download only current catalog files")
    args = parser.parse_args()

    if not args.catalog_only:
        download_group(LEGACY_SOURCES, RAW_DIR, args.force)
    if not args.legacy_only:
        download_group(CATALOG_DATA_URLS, CATALOG_DIR, args.force)
        download_group(CATALOG_METADATA_URLS, CATALOG_DIR, args.force)


if __name__ == "__main__":
    main()
