# TradingView Daily Screener Web Dashboard

This is a Flask dashboard for the existing TradingView screener project.

Expected project layout:

```text
TV_API/
├── TV_screener.py
├── malaysia.db
├── us.db
├── daily_diff.db          # created automatically
└── web/
    ├── app.py
    ├── requirements.txt
    ├── templates/
    │   └── index.html
    └── static/
        └── style.css
```

## What it does

- Malaysia / US tabs
- Same layout for both markets
- Shows the latest 3 scan dates
- Shows all stocks selected by the screener for each day
- Calculates NEW stocks by comparing each scan date with the previous available scan date
- Stores NEW results in `daily_diff.db`
- Handles weekends/market holidays by comparing against the previous available scan date
- Clicking a ticker opens its TradingView page
- Refresh button reloads the latest database data
- `/health` provides a simple health check

## Run on Windows

Open Command Prompt:

```bat
cd C:\Users\Admin\Desktop\TV_API\web
py -m pip install -r requirements.txt
py app.py
```

Then open:

```text
http://localhost:62841
```

The Flask server listens on:

```text
0.0.0.0:62841
```

so it can later be accessed from another device on the same network using:

```text
http://<PC-IP>:62841
```

## Important

The existing `TV_screener.py` is not changed by this dashboard.

The dashboard reads:

```text
..\malaysia.db
..\us.db
```

and creates:

```text
..\daily_diff.db
```

automatically.

## Diff logic

For a scan date:

```text
New stocks =
Current scan tickers
-
Previous available scan tickers
```

Example:

```text
22 Sep: A B C D
23 Sep: A B C E F

New on 23 Sep:
E F
```

Only the latest 3 dates are displayed, but the diff database keeps historical NEW records.


## UI updates

- Added Light/Dark mode toggle.
- Theme preference is saved in browser local storage.
- Each ticker now opens the shared TradingView chart layout:
  `https://www.tradingview.com/chart/d1JfAmuY/?symbol=EXCHANGE%3ATICKER`
- The exchange-qualified ticker returned by TradingView is preserved, e.g.
  `MYX:ECOSHOP` becomes `MYX%3AECOSHOP`.

## Run with Docker on macOS

This project can run continuously on a MacBook with Docker Desktop.

### 1. Start Docker Desktop

Make sure Docker Desktop is running.

### 2. Start the project

From the `TV_API` directory:

```bash
docker compose up -d --build
```

### 3. Open the dashboard

Open:

```text
http://localhost:62841
```

### 4. Check the containers

```bash
docker compose ps
```

You should see:

```text
stock-filter-web
stock-filter-scheduler
```

### 5. View logs

Dashboard:

```bash
docker compose logs -f web
```

Daily screener:

```bash
docker compose logs -f scheduler
```

### Daily schedule

The scheduler runs the screener at **07:00 local Mac/container time** every day.

If the MacBook or Docker containers restart after 07:00 and today's scan is missing, the scheduler runs the screener automatically rather than waiting until the following day.

### Persistent data

The following SQLite databases remain in the project directory:

- `malaysia.db`
- `us.db`
- `daily_diff.db`

The Docker containers mount the project directory, so restarting or rebuilding the containers does not remove your screening history or watchlist.

### Stop the project

```bash
docker compose down
```

### Start it again

```bash
docker compose up -d
```
