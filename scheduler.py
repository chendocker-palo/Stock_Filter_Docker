from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

BASE_DIR = Path(__file__).resolve().parent
SCREENER = BASE_DIR / "TV_screener.py"
DBS = [BASE_DIR / "malaysia.db", BASE_DIR / "us.db"]
RUN_HOUR = 7
RUN_MINUTE = 0


def has_scan_for_today():
    today = datetime.now().strftime("%Y-%m-%d")

    for db_path in DBS:
        if not db_path.exists():
            return False

        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM screening_results
                WHERE scan_date = ?
                LIMIT 1
                """,
                (today,),
            ).fetchone()

        if row is None:
            return False

    return True


def run_screener():
    print("=" * 60, flush=True)
    print(f"Starting daily screener: {datetime.now().isoformat(timespec='seconds')}", flush=True)
    print("=" * 60, flush=True)

    result = subprocess.run(
        [sys.executable, str(SCREENER)],
        cwd=BASE_DIR,
        check=False,
    )

    print(f"Screener exit code: {result.returncode}", flush=True)
    return result.returncode


def seconds_until_next_run():
    now = datetime.now()
    target = now.replace(
        hour=RUN_HOUR,
        minute=RUN_MINUTE,
        second=0,
        microsecond=0,
    )

    if target <= now:
        target += timedelta(days=1)

    return max(1, int((target - now).total_seconds()))


while True:
    if not has_scan_for_today():
        run_screener()
        time.sleep(60)
        continue

    wait_seconds = seconds_until_next_run()
    print(
        f"Today's scan already exists. Next scheduled run in "
        f"{wait_seconds // 3600}h {(wait_seconds % 3600) // 60}m.",
        flush=True,
    )
    time.sleep(wait_seconds)
