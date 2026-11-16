from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_step(label: str, script: str) -> None:
    print(f"\n=== {label} ===", flush=True)
    command = [PYTHON, str(ROOT / script)]
    try:
        subprocess.run(command, cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Step failed: {label} (exit {exc.returncode})") from exc


def app_check() -> None:
    print("\n=== Dashboard smoke test ===", flush=True)
    code = (
        "from src.app import load_dashboard_data, build_app; "
        "app = build_app(load_dashboard_data()); "
        "response = app.server.test_client().get('/'); "
        "print('HTTP', response.status_code); "
        "raise SystemExit(0 if response.status_code == 200 else 1)"
    )
    try:
        subprocess.run([PYTHON, "-c", code], cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Dashboard smoke test failed") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full COVID-19 project pipeline end to end."
    )
    parser.add_argument(
        "--skip-forecast",
        action="store_true",
        help="Skip the expensive model comparison and future forecast step.",
    )
    parser.add_argument(
        "--skip-benchmark",
        action="store_true",
        help="Skip the CSV vs Parquet benchmark.",
    )
    parser.add_argument(
        "--skip-app-check",
        action="store_true",
        help="Skip the Dash HTTP smoke check.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    steps = [
        ("Prepare sample and manifest", "scripts/prepare_data.py"),
        ("Build merged Parquet", "scripts/build_merged_dataset.py"),
        ("Run EDA, waves and figures", "scripts/run_analysis.py"),
        ("Build SQLite database", "scripts/build_sqlite.py"),
        ("Run SQL queries", "scripts/run_sql.py"),
    ]
    if not args.skip_forecast:
        steps.append(("Run forecast comparison", "scripts/run_forecast.py"))
    if not args.skip_benchmark:
        steps.append(("Benchmark CSV vs Parquet", "scripts/benchmark_storage.py"))
    steps.append(("Smoke test artifacts and SQL", "scripts/smoke_test.py"))

    for label, script in steps:
        run_step(label, script)
    if not args.skip_app_check:
        app_check()
    print("\nAll pipeline steps completed successfully.")


if __name__ == "__main__":
    main()
