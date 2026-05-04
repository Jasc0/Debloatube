# Debloatube

![logo](logo.png)

A self-hosted YouTube frontend that scrapes your personalized feed and serves it as a clean, ad-free, dark-themed web UI 

---

## How it works

Debloatube runs a headless Chromium browser (via Selenium) using a **real Chromium profile**, so it scrapes YouTube while logged in as you or a throwaway account. It parses the mobile YouTube HTML (`ytm-*` elements via BeautifulSoup), caches results in a local SQLite database, and serves everything through a HTTP server on port 8080.

The homepage loads instantly from cache, then kicks off a background scrape to refresh it.

---

## Features

- **Personalized feed** — scraped from your actual YouTube account
- **Search** — search YouTube without distractions or promoted content
- **Channel view** — browse any channel's video uploads
- **Watch Later** — built-in watch-later list stored locally in SQLite
- **Hide Video** — permanently remove a video from your feed (stored in DB)
- **Copy link** — click any video card to copy its YouTube URL to clipboard
- **Feed Algorithm** — intentionally "feed" YouTube's algorithm by opening a video URL in the headless browser (useful for steering recommendations)
- **No ads, no Shorts** — Shorts are filtered out at the scraping layer

---

## Requirements

- Python 3
- Chromium installed at `/usr/bin/chromium`
- A logged-in Chromium profile at `~/.config/chromium/Default` (the default location on Linux)
- `systemd` (for the managed service install)

Python dependencies (installed automatically by `make install`):
```
beautifulsoup4==4.14.3
selenium==4.43.0
```

---

## Installation

```bash
git clone <repo-url>
cd Debloatube
make install
```

`make install` will:
1. Create a Python venv at `./debloatube/` and install dependencies
2. Copy the systemd user service to `~/.config/systemd/user/`
3. Enable and start the service

The server will be available at `http://localhost:8080`.

To uninstall:
```bash
make uninstall
```

### Running manually (without systemd)

```bash
make venv
./debloatube.sh
```

---

## Configuration

All configuration is at the top of `main.py`:

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `./debloatube.db` | Path to the SQLite database |
| `HOST` | `0.0.0.0` | Address to bind the HTTP server |
| `PORT` | `8080` | Port to serve on |
| `DEBUG` | `False` | When `True`, dumps scraped HTML to `scrape.html` / `search_scrape.html` |

---

## Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Homepage — serves cached feed, triggers background refresh |
| `GET` | `/search?q=<query>` | Search results |
| `GET` | `/channel/<username>` | Videos from a specific channel |
| `GET` | `/watch_later` | Watch Later list |
| `POST` | `/feed` | Feed the algorithm (opens URL in headless browser) |
| `POST` | `/hide` | Hide a video (sets `hidden = TRUE` in DB) |
| `POST` | `/addwl` | Add a video to Watch Later |
| `POST` | `/rmwl` | Remove a video from Watch Later |

---

## Database schema

```sql
CREATE TABLE stored_videos (
    id        TEXT PRIMARY KEY,  -- YouTube video ID
    url       TEXT NOT NULL,
    title     TEXT,
    author    TEXT,              -- channel handle
    thumbnail TEXT,              -- thumbnail URL
    added     INTEGER,           -- Unix timestamp
    hidden    BOOLEAN,
    uploaded  TEXT               -- relative upload date (e.g. "3 days ago")
);

CREATE TABLE watch_later (
    id     TEXT PRIMARY KEY,     -- YouTube video ID
    added  INTEGER               -- Unix timestamp
);
```

---
