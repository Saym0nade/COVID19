from __future__ import annotations

import json
from pathlib import Path

try:
    from .config import (
        CATALOG_SAMPLE_PATH,
        DB_PATH,
        LEGACY_SAMPLE_PATH,
        MANIFEST_PATH,
        SCHEMA_PATH,
    )
except ImportError:
    from config import (
        CATALOG_SAMPLE_PATH,
        DB_PATH,
        LEGACY_SAMPLE_PATH,
        MANIFEST_PATH,
        SCHEMA_PATH,
    )


def show_status() -> None:
    if not MANIFEST_PATH.exists():
        print("Manifest not found. Run: python scripts/prepare_data.py")
        return
    manifest = json.loads(Path(MANIFEST_PATH).read_text(encoding="utf-8"))
    totals = manifest["totals"]
    primary = manifest.get("primary_dataset", manifest.get("main_dataset"))
    legacy = manifest.get("legacy_dataset")
    volume = manifest.get("volume_requirement", {})
    print("COVID-19 Global Dynamics")
    print(f"Legacy files: {totals.get('legacy_files', 0)}")
    print(f"Catalog files: {totals.get('catalog_files', 0)}")
    print(f"Legacy rows: {totals.get('legacy_rows', 0)}")
    print(f"Catalog rows: {totals.get('catalog_rows', 0)}")
    print(f"Combined data: {totals.get('data_rows', 0)} rows, {totals.get('data_megabytes', 0)} MB")
    print(f"Volume requirement: {'OK' if volume.get('satisfied') else 'NOT MET'}")
    if primary:
        print(f"Primary dataset: {primary['path']} ({primary['rows']} rows, {primary['megabytes']} MB)")
    if legacy:
        print(f"Legacy fallback: {legacy['path']} ({legacy['rows']} rows, {legacy['megabytes']} MB)")
    print(f"Catalog sample: {CATALOG_SAMPLE_PATH}")
    print(f"Legacy sample: {LEGACY_SAMPLE_PATH}")
    print(f"Database path: {DB_PATH}")
    print(f"Schema path: {SCHEMA_PATH}")


def main() -> None:
    while True:
        print()
        print("1 - Show data status")
        print("2 - Show dashboard launch command")
        print("3 - Exit")
        try:
            choice = input("Select an option: ").strip()
            if choice == "1":
                show_status()
            elif choice == "2":
                print("Run: python -m src.app")
            elif choice == "3":
                print("Exit.")
                break
            else:
                print("Unknown option.")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
