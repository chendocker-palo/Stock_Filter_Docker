from tradingview_screener import Query, col


def main():
    print("Querying TradingView...")
    print()

    count, df = (
        Query()
        .select(
            "name",
            "description",
            "exchange",
            "close",
            "volume",
            "market_cap_basic",
            "EMA20",
            "EMA50",
            "RSI",
        )
        .where(
            col("close") > 5,
            col("volume") > 1_000_000,
            col("close") > col("EMA20"),
            col("EMA20") > col("EMA50"),
        )
        .order_by("volume", ascending=False)
        .limit(100)
        .get_scanner_data()
    )

    print(f"Total matching stocks: {count}")
    print(f"Rows returned: {len(df)}")
    print()

    print(df.to_string(index=False))

    df.to_csv("tradingview_results.csv", index=False)

    print()
    print("Results saved to: tradingview_results.csv")


if __name__ == "__main__":
    main()