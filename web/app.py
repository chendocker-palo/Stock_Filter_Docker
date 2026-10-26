from pathlib import Path
from datetime import datetime
import sqlite3

from flask import Flask, jsonify, render_template, request


# ============================================================
# Paths
# ============================================================

WEB_DIR = Path(__file__).resolve().parent
PROJECT_DIR = WEB_DIR.parent

MALAYSIA_DB = PROJECT_DIR / "malaysia.db"
US_DB = PROJECT_DIR / "us.db"
DIFF_DB = PROJECT_DIR / "daily_diff.db"

DEFAULT_DAYS = 3
MAX_DAYS = 3650


# ============================================================
# Flask
# ============================================================

app = Flask(__name__)


# ============================================================
# Database helpers
# ============================================================

def initialize_diff_database():
    """Create the daily diff and watchlist tables if they do not exist."""
    with sqlite3.connect(DIFF_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_diff (
                market TEXT NOT NULL,
                scan_date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                name TEXT,
                description TEXT,
                close REAL,
                volume REAL,
                previous_date TEXT,
                change_type TEXT NOT NULL,
                UNIQUE(market, scan_date, ticker, change_type)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                market TEXT NOT NULL,
                ticker TEXT NOT NULL,
                name TEXT,
                description TEXT,
                added_at TEXT NOT NULL,
                UNIQUE(market, ticker)
            )
            """
        )

        conn.commit()


def get_scan_dates(db_path):
    """Return available scan dates, newest first."""
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT scan_date
            FROM screening_results
            ORDER BY scan_date DESC
            """
        ).fetchall()

    return [row[0] for row in rows]


def get_results_for_date(db_path, scan_date):
    """Return all screening results for one date."""
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                ticker,
                name,
                description,
                close,
                volume
            FROM screening_results
            WHERE scan_date = ?
            ORDER BY volume DESC, ticker ASC
            """,
            (scan_date,),
        ).fetchall()

    return [dict(row) for row in rows]


def rebuild_diff_for_market(market, db_path):
    """
    Build NEW-stock records from the screening database.

    The comparison uses the previous available scan date rather than
    assuming that every calendar day has a scan. This handles weekends
    and market holidays naturally.
    """
    dates = get_scan_dates(db_path)

    if not dates:
        return

    with sqlite3.connect(DIFF_DB) as conn:
        for index, scan_date in enumerate(dates):
            if index + 1 >= len(dates):
                # Oldest available date has no previous scan to compare.
                continue

            previous_date = dates[index + 1]

            current_rows = get_results_for_date(db_path, scan_date)
            previous_rows = get_results_for_date(db_path, previous_date)

            previous_tickers = {
                row["ticker"]
                for row in previous_rows
            }

            for row in current_rows:
                ticker = row["ticker"]

                if ticker in previous_tickers:
                    continue

                conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_diff
                    (
                        market,
                        scan_date,
                        ticker,
                        name,
                        description,
                        close,
                        volume,
                        previous_date,
                        change_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        market,
                        scan_date,
                        ticker,
                        row.get("name"),
                        row.get("description"),
                        row.get("close"),
                        row.get("volume"),
                        previous_date,
                        "NEW",
                    ),
                )

        conn.commit()


def refresh_all_diffs():
    """Refresh both market diff data."""
    initialize_diff_database()

    rebuild_diff_for_market("Malaysia", MALAYSIA_DB)
    rebuild_diff_for_market("US", US_DB)


def get_new_stocks(market, scan_date):
    """Return stocks that are NEW on a particular scan date."""
    with sqlite3.connect(DIFF_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                ticker,
                name,
                description,
                close,
                volume,
                previous_date
            FROM daily_diff
            WHERE market = ?
              AND scan_date = ?
              AND change_type = 'NEW'
            ORDER BY volume DESC, ticker ASC
            """,
            (market, scan_date),
        ).fetchall()

    return [dict(row) for row in rows]


def get_watchlist():
    """Return all permanently saved watchlist stocks."""
    with sqlite3.connect(DIFF_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                market,
                ticker,
                name,
                description,
                added_at
            FROM watchlist
            ORDER BY market ASC, ticker ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def add_to_watchlist(market, ticker, name=None, description=None):
    """Add a stock to the permanent watchlist."""
    with sqlite3.connect(DIFF_DB) as conn:
        conn.execute(
            """
            INSERT INTO watchlist
            (
                market,
                ticker,
                name,
                description,
                added_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(market, ticker)
            DO UPDATE SET
                name = excluded.name,
                description = excluded.description
            """,
            (
                market,
                ticker,
                name,
                description,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()


def remove_from_watchlist(market, ticker):
    """Remove a stock from the permanent watchlist."""
    with sqlite3.connect(DIFF_DB) as conn:
        conn.execute(
            """
            DELETE FROM watchlist
            WHERE market = ?
              AND ticker = ?
            """,
            (market, ticker),
        )
        conn.commit()


def parse_days(value):
    """Return a safe number of scan days requested by the UI."""
    if value is None or value == "":
        return DEFAULT_DAYS

    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DAYS

    return max(1, min(days, MAX_DAYS))


# ============================================================
# Market configuration
# ============================================================

MARKETS = {
    "malaysia": {
        "label": "Malaysia",
        "db": MALAYSIA_DB,
        "currency": "RM",
        "filters": [
            "Market: Malaysia",
            "Market cap: RM 1 billion to RM 200 billion",
            "Close > EMA 20",
            "EMA 10 > EMA 20",
            "EMA 20 > EMA 50",
            "Close > Weekly EMA 20",
            "Close > EMA 10",
            "Primary listings only",
            "Common stocks only",
        ],
    },
    "us": {
        "label": "US",
        "db": US_DB,
        "currency": "USD",
        "filters": [
            "Market: America / US",
            "Market cap: USD 50 billion and above",
            "Exchange: NYSE, NASDAQ, AMEX",
            "Close > EMA 20",
            "EMA 10 > EMA 20",
            "EMA 20 > EMA 50",
            "Close > Weekly EMA 20",
            "Close > EMA 10",
            "Primary listings only",
            "Common stocks only",
            "OTC excluded",
        ],
    },
}


# ============================================================
# API
# ============================================================

def build_market_data(market_key, days=DEFAULT_DAYS):
    market = MARKETS[market_key]
    dates = get_scan_dates(market["db"])[:days]

    watchlist = {
        (item["market"], item["ticker"])
        for item in get_watchlist()
    }

    days_data = []

    for scan_date in dates:
        results = get_results_for_date(
            market["db"],
            scan_date,
        )

        for stock in results:
            stock["watchlisted"] = (
                market["label"],
                stock["ticker"],
            ) in watchlist

        new_stocks = get_new_stocks(
            market["label"],
            scan_date,
        )

        for stock in new_stocks:
            stock["watchlisted"] = (
                market["label"],
                stock["ticker"],
            ) in watchlist

        days_data.append(
            {
                "date": scan_date,
                "results": results,
                "new": new_stocks,
                "count": len(results),
                "new_count": len(new_stocks),
            }
        )

    return {
        "market": market["label"],
        "currency": market["currency"],
        "filters": market["filters"],
        "days": days_data,
        "days_requested": days,
    }


@app.get("/")
def index():
    refresh_all_diffs()

    return render_template(
        "index.html",
        markets=MARKETS,
    )


@app.get("/api/<market_key>")
def market_api(market_key):
    if market_key not in MARKETS:
        return jsonify({"error": "Unknown market"}), 404

    days = parse_days(request.args.get("days"))

    refresh_all_diffs()

    return jsonify(build_market_data(market_key, days))


@app.get("/api/watchlist")
def watchlist_api():
    initialize_diff_database()

    return jsonify(
        {
            "watchlist": get_watchlist(),
        }
    )


@app.post("/api/watchlist")
def add_watchlist_api():
    initialize_diff_database()

    data = request.get_json(silent=True) or {}

    market = str(data.get("market", "")).strip()
    ticker = str(data.get("ticker", "")).strip()

    if market not in {"Malaysia", "US"} or not ticker:
        return jsonify({"error": "Invalid market or ticker"}), 400

    add_to_watchlist(
        market=market,
        ticker=ticker,
        name=data.get("name"),
        description=data.get("description"),
    )

    return jsonify({"success": True})


@app.delete("/api/watchlist")
def delete_watchlist_api():
    initialize_diff_database()

    data = request.get_json(silent=True) or {}

    market = str(data.get("market", "")).strip()
    ticker = str(data.get("ticker", "")).strip()

    if market not in {"Malaysia", "US"} or not ticker:
        return jsonify({"error": "Invalid market or ticker"}), 400

    remove_from_watchlist(market, ticker)

    return jsonify({"success": True})


@app.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "time": datetime.now().isoformat(timespec="seconds"),
            "malaysia_db": MALAYSIA_DB.exists(),
            "us_db": US_DB.exists(),
            "diff_db": DIFF_DB.exists(),
        }
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    initialize_diff_database()

    app.run(
        host="0.0.0.0",
        port=62841,
        debug=False,
    )
