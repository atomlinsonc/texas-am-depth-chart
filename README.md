# Texas A&M Football Depth Chart

Static GitHub Pages app for an interactive Texas A&M football depth chart with:

- offense and defense shown in on-field formation layouts
- starter / second-string / third-string toggles
- player badges and modeled 0-100 "PFF-style" ratings
- latest available player stats and bios
- coach bios and tendency summaries
- weekly automated data refresh via GitHub Actions

## Data sources

- ESPN roster API: roster metadata and headshots
- ESPN team stats page: latest available player stats
- Ourlads depth chart: starter / backup depth rows
- Texas A&M 12thMan: player bios and coach bios
- web-sourced coach tendency references linked in the generated JSON

## Ratings note

The player ratings in this project are not official Pro Football Focus grades.
They are modeled 0-100 "PFF-style" grades derived from public stats and role data
to approximate snap-level contribution signals by position.

## Local usage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/update_data.py
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

## Automation

- `update-data.yml` refreshes data every Monday via cron and on manual dispatch.
- `deploy.yml` deploys the static site to GitHub Pages on pushes to `main`.
