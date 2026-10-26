from pathlib import Path
from datetime import datetime
import sqlite3

from tradingview_screener import stocks, col


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MALAYSIA_DB = BASE_DIR / "malaysia.db"
US_DB = BASE_DIR / "us.db"

# Malaysia market cap:
# RM 1 billion to RM 200 billion
MALAYSIA_MIN_MARKET_CAP = 1_000_000_000
MALAYSIA_MAX_MARKET_CAP = 200_000_000_000

# US market cap:
# USD 50 billion and above
US_MIN_MARKET_CAP = 50_000_000_000

# Maximum number of results
RESULT_LIMIT = 1000


# ============================================================
# Database
# ============================================================

def initialize_database(db_path):
    """
    Create the SQLite database and table if they do not exist.
    """

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS screening_results (
                scan_date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                name TEXT,
                description TEXT,
                close REAL,
                volume REAL,
                UNIQUE(scan_date, ticker)
            )
            """
        )

        conn.commit()


# ============================================================
# Malaysia Screener
# ============================================================

def run_malaysia_screener():
    """
    Run the TradingView Malaysia Stock Screener.
    """

    print("\n" + "=" * 60)
    print("MALAYSIA SCREENER")
    print("=" * 60)

    query = (
        stocks("malaysia")
        .select(
            "name",
            "description",
            "close",
            "volume",
        )
        .where(
            # Primary listings only
            col("is_primary") == True,

            # Common stocks only
            col("type") == "stock",
            col("typespecs").has(["common"]),

            # Market capitalization:
            # RM 1 billion to RM 200 billion
            col("market_cap_basic") >= MALAYSIA_MIN_MARKET_CAP,
            col("market_cap_basic") <= MALAYSIA_MAX_MARKET_CAP,

            # Price > EMA 20
            col("close") > col("EMA20"),

            # EMA 10 > EMA 20
            col("EMA10") > col("EMA20"),

            # EMA 20 > EMA 50
            col("EMA20") > col("EMA50"),

            # Price > Weekly EMA 20
            col("close") > col("EMA20|1W"),

            # Price > EMA 10
            col("close") > col("EMA10"),
        )
        .order_by("volume", ascending=False)
        .limit(RESULT_LIMIT)
    )

    count, df = query.get_scanner_data()

    print(f"TradingView matching stocks: {count}")
    print(f"Returned rows: {len(df)}")

    return df


# ============================================================
# US Screener
# ============================================================

def run_us_screener():
    """
    Run the TradingView US Stock Screener.

    Only:
        NYSE
        NASDAQ
        AMEX

    Common stocks only.
    OTC, preferred shares and ETFs are excluded.
    """

    print("\n" + "=" * 60)
    print("US SCREENER")
    print("=" * 60)

    query = (
        stocks("america")
        .select(
            "name",
            "description",
            "close",
            "volume",
        )
        .where(
            # Primary listings only
            col("is_primary") == True,

            # Common stocks only
            col("type") == "stock",
            col("typespecs").has(["common"]),

            # Only NYSE, NASDAQ and AMEX
            col("exchange").isin(
                [
                    "NYSE",
                    "NASDAQ",
                    "AMEX",
                ]
            ),

            # Market capitalization:
            # USD 50 billion and above
            col("market_cap_basic") >= US_MIN_MARKET_CAP,

            # Price > EMA 20
            col("close") > col("EMA20"),

            # EMA 10 > EMA 20
            col("EMA10") > col("EMA20"),

            # EMA 20 > EMA 50
            col("EMA20") > col("EMA50"),

            # Price > Weekly EMA 20
            col("close") > col("EMA20|1W"),

            # Price > EMA 10
            col("close") > col("EMA10"),
        )
        .order_by("volume", ascending=False)
        .limit(RESULT_LIMIT)
    )

    count, df = query.get_scanner_data()

    print(f"TradingView matching stocks: {count}")
    print(f"Returned rows: {len(df)}")

    return df


# ============================================================
# Save Results
# ============================================================

def save_results(db_path, df, scan_date):
    """
    Save screener results into SQLite.

    A ticker can only be saved once per scan date.
    """

    if df.empty:
        print("No matching stocks to save.")
        return 0

    saved_count = 0

    with sqlite3.connect(db_path) as conn:

        for _, row in df.iterrows():

            ticker = row["ticker"]

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO screening_results
                (
                    scan_date,
                    ticker,
                    name,
                    description,
                    close,
                    volume
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_date,
                    str(ticker),
                    row.get("name"),
                    row.get("description"),
                    row.get("close"),
                    row.get("volume"),
                ),
            )

            if cursor.rowcount == 1:
                saved_count += 1

        conn.commit()

    return saved_count


# ============================================================
# Display Results
# ============================================================

def display_results(df):
    """
    Print matching stocks to the terminal.
    """

    if df.empty:
        print("\nNo stocks matched the filters.")
        return

    display_columns = [
        "ticker",
        "name",
        "description",
        "close",
        "volume",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in df.columns
    ]

    print("\nMatching stocks:")
    print("-" * 100)

    print(
        df[display_columns].to_string(index=False)
    )


# ============================================================
# Main
# ============================================================

def main():

    scan_date = datetime.now().strftime("%Y-%m-%d")

    print("\n" + "=" * 60)
    print("TRADINGVIEW DAILY SCREENER")
    print("=" * 60)

    print(f"Scan date: {scan_date}")
    print(f"Database directory: {BASE_DIR}")

    # --------------------------------------------------------
    # Initialize databases
    # --------------------------------------------------------

    initialize_database(MALAYSIA_DB)
    initialize_database(US_DB)

    print(
        f"\nMalaysia database: {MALAYSIA_DB}"
    )

    print(
        f"US database:       {US_DB}"
    )

    # --------------------------------------------------------
    # Malaysia
    # --------------------------------------------------------

    try:

        malaysia_df = run_malaysia_screener()

        display_results(malaysia_df)

        malaysia_saved = save_results(
            MALAYSIA_DB,
            malaysia_df,
            scan_date,
        )

        print(
            f"\nMalaysia records saved: {malaysia_saved}"
        )

    except Exception as exc:

        print("\nMalaysia screener failed:")
        print(exc)

    # --------------------------------------------------------
    # US
    # --------------------------------------------------------

    try:

        us_df = run_us_screener()

        display_results(us_df)

        us_saved = save_results(
            US_DB,
            us_df,
            scan_date,
        )

        print(
            f"\nUS records saved: {us_saved}"
        )

    except Exception as exc:

        print("\nUS screener failed:")
        print(exc)

    # --------------------------------------------------------
    # Finished
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("SCREENING COMPLETE")
    print("=" * 60)

    print(f"Date: {scan_date}")

    print(
        f"Malaysia DB: {MALAYSIA_DB}"
    )

    print(
        f"US DB:       {US_DB}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()