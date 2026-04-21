#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

TEAM_NAME = "Texas A&M Aggies"
TEAM_ID = 245
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "aggies.json"

ESPN_ROSTER_URL = (
    f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{TEAM_ID}/roster"
)
ESPN_TEAM_STATS_URL = (
    f"https://www.espn.com/college-football/team/stats/_/id/{TEAM_ID}/texas-am-aggies"
)
OURLADS_DEPTH_URL = "https://www.ourlads.com/ncaa-football-depth-charts/pfdepthchart/texas-am/92039"
OURLADS_SECURE_DEPTH_URL = "https://secure.ourlads.com/ncaa-football-depth-charts/depth-chart/texas-am/92039"
TWELFTHMAN_ROSTER_URL = "https://12thman.com/sports/football/roster"
CFBSTATS_TEAM_URL = "https://cfbstats.com/{season}/team/697/index.html"
COACH_URLS = {
    "Mike Elko": "https://12thman.com/sports/football/roster/coaches/mike-elko/2151",
    "Holmon Wiggins": "https://12thman.com/sports/football/roster/coaches/holmon-wiggins/2158",
    "Lyle Hemphill": "https://12thman.com/sports/football/roster/coaches/lyle-hemphill/1990",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

RATING_CSV_PATHS = {
    "rushing": Path.home() / "Downloads" / "rushing_summary.csv",
    "receiving": Path.home() / "Downloads" / "receiving_summary.csv",
    "passing": Path.home() / "Downloads" / "passing_summary.csv",
    "blocking": Path.home() / "Downloads" / "offense_blocking.csv",
    "defense": Path.home() / "Downloads" / "defense_summary.csv",
}

OFFENSE_LAYOUT = {
    "WR-X": {"x": 10, "y": 58},
    "WR-SL": {"x": 22, "y": 71},
    "LT": {"x": 34, "y": 58},
    "LG": {"x": 42, "y": 58},
    "C": {"x": 50, "y": 58},
    "RG": {"x": 58, "y": 58},
    "RT": {"x": 66, "y": 58},
    "TE": {"x": 80, "y": 71},
    "QB": {"x": 50, "y": 81},
    "RB": {"x": 56, "y": 93},
    "WR-Z": {"x": 90, "y": 58},
}

DEFENSE_LAYOUT = {
    "FS": {"x": 35, "y": 20},
    "SS": {"x": 67, "y": 24},
    "WLB": {"x": 43, "y": 36},
    "MLB": {"x": 57, "y": 36},
    "NB": {"x": 23, "y": 50},
    "LDE": {"x": 34, "y": 45},
    "NT": {"x": 46, "y": 45},
    "DT": {"x": 56, "y": 45},
    "RDE": {"x": 68, "y": 45},
    "LCB": {"x": 10, "y": 58},
    "RCB": {"x": 90, "y": 58},
}

COACH_TENDENCIES = {
    "Mike Elko": {
        "role": "Head Coach",
        "tendencies": [
            "Aggressive on selected fourth downs compared with the prior staff, especially when the offense has a matchup edge.",
            "Defensive identity leans on split-front looks and variable pressure packages instead of one static structure.",
            "Program emphasis is complementary football: explosive run game support on offense and third-down efficiency on defense.",
        ],
        "sources": [
            {
                "label": "KBTX on fourth-down aggressiveness",
                "url": "https://www.kbtx.com/2024/11/08/fourth-down-attempts-more-commonplace-texas-am-football-elko-era/",
            },
            {
                "label": "MatchQuarters on Elko split-front pressure philosophy",
                "url": "https://www.matchquarters.com/p/mike-elkos-split-front",
            },
            {
                "label": "Official Texas A&M bio",
                "url": COACH_URLS["Mike Elko"],
            },
        ],
    },
    "Holmon Wiggins": {
        "role": "Offensive Coordinator",
        "tendencies": [
            "Receiver-driven approach that leans into explosive catches and vertical efficiency.",
            "Emphasis on wideout development and route detail, with a track record of producing high-end receiver output.",
            "Focus on red-zone and third-down efficiency while preserving continuity from the Aggies' 2024-25 offensive structure.",
        ],
        "sources": [
            {
                "label": "Texas A&M promotion announcement",
                "url": "https://12thman.com/news/2025/12/17/football-elko-announces-promotion-of-wiggins-to-offensive-coordinator",
            },
            {
                "label": "Official Texas A&M bio",
                "url": COACH_URLS["Holmon Wiggins"],
            },
            {
                "label": "2026 Texas A&M coaches page",
                "url": "https://12thman.com/sports/football/coaches",
            },
        ],
    },
    "Lyle Hemphill": {
        "role": "Defensive Coordinator",
        "tendencies": [
            "Secondary-driven structure with flexible shells that can rotate late and disguise coverage.",
            "Pressure complements coverage rather than replacing it; the goal is to win on passing downs without living in all-out blitz.",
            "Strong emphasis on limiting explosive passes while winning third-down situations.",
        ],
        "sources": [
            {
                "label": "Texas A&M promotion announcement",
                "url": "https://12thman.com/news/2025/12/12/football-elko-elevates-hemphill-to-aggies-next-defensive-coordinator",
            },
            {
                "label": "Wake Forest defensive overview",
                "url": "https://www.shakinthesouthland.com/2020/9/11/21429614/what-to-watch-for-in-the-wake-forest-defense",
            },
            {
                "label": "Official Texas A&M bio",
                "url": COACH_URLS["Lyle Hemphill"],
            },
        ],
    },
}

CLASS_TOKENS = {
    "FR",
    "SO",
    "JR",
    "SR",
    "GR",
    "TR",
    "RS",
}
SUFFIX_TOKENS = {"JR", "SR", "II", "III", "IV", "V"}
POSITION_GROUPS = {
    "QB": "quarterback",
    "RB": "running_back",
    "WR": "receiver",
    "TE": "receiver",
    "OL": "offensive_line",
    "LT": "offensive_line",
    "LG": "offensive_line",
    "C": "offensive_line",
    "RG": "offensive_line",
    "RT": "offensive_line",
    "DL": "front_seven",
    "DE": "front_seven",
    "DT": "front_seven",
    "NT": "front_seven",
    "LB": "front_seven",
    "CB": "defensive_back",
    "S": "defensive_back",
    "DB": "defensive_back",
    "K": "specialist",
    "P": "specialist",
}


def fetch_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=45)
    response.raise_for_status()
    return response.text


def fetch_json(url: str) -> Any:
    response = requests.get(url, headers=HEADERS, timeout=45)
    response.raise_for_status()
    return response.json()


def normalize_name(name: str) -> str:
    value = unescape(name).lower().replace("&amp;", "and")
    value = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def compact_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unescape(name or "").lower())


def slugify(value: str) -> str:
    return normalize_name(value).replace(" ", "-")


def trim_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_espn_fitt_json(html: str) -> dict[str, Any]:
    match = re.search(r"window\['__espnfitt__'\]=(\{.*?\});</script>", html, re.S)
    if not match:
        raise RuntimeError("Could not locate ESPN payload")
    return json.loads(match.group(1))


def parse_ourlads_player_text(raw_text: str) -> tuple[str, str]:
    text = trim_text(raw_text)
    parts = text.split()
    eligibility_tokens: list[str] = []
    while parts:
        token_parts = [segment for segment in parts[-1].upper().split("/") if segment]
        if token_parts and all(segment in CLASS_TOKENS for segment in token_parts):
            eligibility_tokens.insert(0, parts.pop())
            continue
        break
    while parts and parts[-1].upper() == "RS":
        eligibility_tokens.insert(0, parts.pop())
    name = " ".join(parts)
    if "," in name:
        last, first = [segment.strip() for segment in name.split(",", 1)]
        name = f"{first} {last}".strip()
    return name, " ".join(eligibility_tokens)


def parse_depth_table(tbody: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in tbody.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        position = trim_text(cells[0].get_text(" ", strip=True))
        players = []
        for idx in range(1, len(cells), 2):
            if idx + 1 >= len(cells):
                continue
            jersey = trim_text(cells[idx].get_text(" ", strip=True))
            anchor = cells[idx + 1].find("a")
            if not anchor:
                continue
            raw_name = trim_text(anchor.get_text(" ", strip=True))
            if not raw_name:
                continue
            player_name, eligibility = parse_ourlads_player_text(raw_name)
            player_url = anchor.get("href") or ""
            if player_url.endswith("/0"):
                continue
            players.append(
                {
                    "name": player_name,
                    "eligibility": eligibility,
                    "jersey": jersey or None,
                    "sourceUrl": player_url,
                }
            )
        rows.append({"position": position, "players": players[:3]})
    return rows


def parse_ourlads_pf_lookup(html: str) -> dict[str, dict[str, list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    lookup: dict[str, dict[str, list[str]]] = {"offense": {}, "defense": {}}
    current_section = ""
    for row in soup.select("#gvChart tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        if len(cells) == 1:
            label = trim_text(cells[0].get_text(" ", strip=True)).lower()
            if label in {"offense", "defense"}:
                current_section = label
            elif label == "special teams":
                break
            continue
        if current_section not in lookup:
            continue
        position = trim_text(cells[0].get_text(" ", strip=True))
        names = []
        for idx in range(2, len(cells), 2):
            anchor = cells[idx].find("a")
            if anchor:
                names.append(compact_name(anchor.get_text(" ", strip=True)))
        if names:
            lookup[current_section][position] = names
    return lookup


def apply_ourlads_verification(
    rows: list[dict[str, Any]], verified_positions: dict[str, list[str]]
) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    for row in rows:
        desired = verified_positions.get(row["position"], [])
        if not desired:
            adjusted.append({**row, "players": row["players"][:3]})
            continue
        players_by_key = {compact_name(player["name"]): player for player in row["players"]}
        ordered: list[dict[str, Any]] = []
        used: set[str] = set()
        for key in desired[:3]:
            player = players_by_key.get(key)
            if player:
                ordered.append(player)
                used.add(key)
        for player in row["players"]:
            key = compact_name(player["name"])
            if key not in used:
                ordered.append(player)
        adjusted.append({**row, "players": ordered[:3]})
    return adjusted


def parse_ourlads_depth(html: str, pf_html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    headings = soup.select("h2.TXAM")
    schemes = {}
    for heading in headings:
        label = trim_text(heading.get_text(" ", strip=True))
        if label.startswith("Offense"):
            schemes["offense"] = trim_text(heading.small.get_text(" ", strip=True)) if heading.small else ""
        if label.startswith("Defense"):
            schemes["defense"] = trim_text(heading.small.get_text(" ", strip=True)) if heading.small else ""

    updated_match = re.search(r"Updated:\s*([0-9/:\sAPMET]+)", html)
    updated_at = trim_text(updated_match.group(1)) if updated_match else ""

    offense_tbody = soup.select_one("#ctl00_phContent_dcTBody")
    defense_tbody = soup.select_one("#ctl00_phContent_dcTBody2")
    if not offense_tbody or not defense_tbody:
        raise RuntimeError("Could not parse Ourlads depth chart tables")
    verified_lookup = parse_ourlads_pf_lookup(pf_html)
    offense_rows = apply_ourlads_verification(parse_depth_table(offense_tbody), verified_lookup["offense"])
    defense_rows = apply_ourlads_verification(parse_depth_table(defense_tbody), verified_lookup["defense"])

    return {
        "updatedAt": updated_at,
        "offenseScheme": schemes.get("offense", ""),
        "defenseScheme": schemes.get("defense", ""),
        "offense": offense_rows,
        "defense": defense_rows,
        "source": {
            "label": "Ourlads printer-friendly depth chart",
            "url": OURLADS_DEPTH_URL,
        },
    }


def parse_espn_roster() -> dict[str, Any]:
    roster = fetch_json(ESPN_ROSTER_URL)
    athletes: dict[str, Any] = {}
    for group in roster.get("athletes", []):
        unit = group.get("position")
        for item in group.get("items", []):
            full_name = item.get("fullName") or item.get("displayName")
            if not full_name:
                continue
            key = normalize_name(full_name)
            stats_link = next(
                (link["href"] for link in item.get("links", []) if "/player/stats/" in link.get("href", "")),
                None,
            )
            athletes[key] = {
                "espnId": item.get("id"),
                "name": full_name,
                "shortName": item.get("shortName"),
                "displayName": item.get("displayName"),
                "positionLabel": item.get("position", {}).get("abbreviation"),
                "unit": unit,
                "height": item.get("displayHeight"),
                "weight": item.get("displayWeight"),
                "heightInches": item.get("height"),
                "weightPounds": item.get("weight"),
                "headshot": item.get("headshot", {}).get("href") if isinstance(item.get("headshot"), dict) else None,
                "jersey": item.get("jersey"),
                "collegeClass": item.get("college", {}).get("shortDisplayName")
                if isinstance(item.get("college"), dict)
                else None,
                "status": item.get("status", {}).get("name") if isinstance(item.get("status"), dict) else None,
                "espnPlayerUrl": next(
                    (link["href"] for link in item.get("links", []) if "/player/_/" in link.get("href", "")),
                    None,
                ),
                "espnStatsUrl": stats_link,
            }
    return {
        "season": roster.get("season", {}),
        "athletes": athletes,
        "source": {"label": "ESPN roster API", "url": ESPN_ROSTER_URL},
    }


def parse_espn_team_stats(html: str) -> dict[str, Any]:
    payload = extract_espn_fitt_json(html)
    stats_content = payload["page"]["content"]["stats"]
    title_match = re.search(r"<title>\s*Texas A&M Aggies\s+(\d{4})\s+College Football Players Stats\s+- ESPN", html)
    stat_season = title_match.group(1) if title_match else ""

    player_stats: dict[str, Any] = {}
    for group in stats_content.get("playerStats", []):
        for entry in group:
            athlete = entry.get("athlete", {})
            name = athlete.get("name")
            if not name:
                continue
            key = normalize_name(name)
            existing = player_stats.setdefault(
                key,
                {
                    "name": name,
                    "espnPlayerUrl": athlete.get("href"),
                    "headshot": athlete.get("headshot"),
                    "position": athlete.get("position"),
                    "statGroups": {},
                },
            )
            stat_group = entry.get("statGroups", {})
            group_type = stat_group.get("type", "unknown")
            if isinstance(group_type, list):
                group_type = group_type[0] if group_type else "unknown"
            if not isinstance(group_type, str):
                group_type = "unknown"
            existing["statGroups"][group_type] = {
                "title": stat_group.get("title"),
                "stats": {
                    stat["name"]: {
                        "value": stat.get("value"),
                        "displayValue": stat.get("displayValue"),
                        "abbreviation": stat.get("abbreviation"),
                    }
                    for stat in stat_group.get("stats", [])
                    if stat.get("name")
                },
            }

    return {
        "season": stat_season,
        "players": player_stats,
        "source": {"label": "ESPN team stats", "url": ESPN_TEAM_STATS_URL},
    }


def parse_12thman_roster_index(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    links: dict[str, str] = {}
    for anchor in soup.select('a[href^="/sports/football/roster/"]'):
        href = anchor.get("href") or ""
        if "/coaches/" in href:
            continue
        if not re.search(r"/sports/football/roster/[^/]+/\d+$", href):
            continue
        label = trim_text(anchor.get_text(" ", strip=True))
        classes = set(anchor.get("class") or [])
        if not {"hover:underline", "focus:underline"}.issubset(classes):
            continue
        if label.startswith("Full Bio for"):
            continue
        if not label or len(label) < 3:
            continue
        links[normalize_name(label)] = urljoin("https://12thman.com", href)
    return links


def clean_plain_text(text: str) -> str:
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_12thman_person(url: str) -> dict[str, Any]:
    html = fetch_text(url)
    soup = BeautifulSoup(html, "html.parser")

    title = trim_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    bio_block = soup.select_one(".s-text-paragraph-longform")
    bio_text = clean_plain_text(bio_block.get_text(" ", strip=True)) if bio_block else ""

    fields: dict[str, str] = {}
    for dt in soup.find_all("dt"):
        label = clean_plain_text(dt.get_text(" ", strip=True)).rstrip(":")
        dd = dt.find_next_sibling("dd")
        if label and dd:
            fields[label] = clean_plain_text(dd.get_text(" ", strip=True))

    headshot = None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.get_text(strip=True))
        except json.JSONDecodeError:
            continue
        main_entity = payload.get("mainEntity") if isinstance(payload, dict) else None
        image = main_entity.get("image") if isinstance(main_entity, dict) else None
        if isinstance(image, str) and image and "site/site.png" not in image:
            headshot = urljoin(url, image)
            break
    if not headshot:
        roster_headshot = soup.select_one('.c-rosterbio__player__image img[src]')
        if roster_headshot and roster_headshot.get("src"):
            headshot = urljoin(url, roster_headshot.get("src"))
    if not headshot:
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content") and "site/site.png" not in og_image.get("content", ""):
            headshot = og_image.get("content")
    if not headshot:
        image = soup.find("img", src=True)
        if image:
            headshot = urljoin(url, image.get("src"))

    return {
        "sourceUrl": url,
        "pageTitle": title,
        "bio": bio_text,
        "bioShort": bio_text[:420].rsplit(" ", 1)[0] + "..." if len(bio_text) > 420 else bio_text,
        "fields": fields,
        "headshot": headshot,
    }


def guess_position_group(position: str) -> str:
    if position in OFFENSE_LAYOUT:
        if position.startswith("WR"):
            return "receiver"
        if position in {"LT", "LG", "C", "RG", "RT"}:
            return "offensive_line"
        if position == "QB":
            return "quarterback"
        if position == "RB":
            return "running_back"
        if position == "TE":
            return "receiver"
    if position in DEFENSE_LAYOUT:
        if position in {"LCB", "RCB", "NB", "SS", "FS"}:
            return "defensive_back"
        return "front_seven"
    return "general"


def numeric_stat(stat_groups: dict[str, Any], group_name: str, stat_name: str) -> float:
    group = stat_groups.get(group_name, {})
    stat = group.get("stats", {}).get(stat_name, {})
    value = stat.get("value")
    if value in ("", None):
        return 0.0
    return float(value)


def year_score(eligibility: str) -> float:
    value = eligibility.upper()
    if "GR" in value:
        return 1.0
    if "SR" in value:
        return 0.9
    if "JR" in value:
        return 0.75
    if "SO" in value:
        return 0.55
    if "FR" in value:
        return 0.4
    return 0.5


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_float(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sample_size(row: dict[str, str]) -> float:
    for key in (
        "snap_counts_defense",
        "snap_counts_offense",
        "dropbacks",
        "attempts",
        "routes",
        "targets",
        "snap_counts_pass_block",
        "run_plays",
        "player_game_count",
    ):
        value = parse_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def load_csv_database() -> dict[str, Any]:
    database: dict[str, Any] = {"sources": {}, "players": {}}
    for source_name, path in RATING_CSV_PATHS.items():
        if not path.exists():
            continue
        rows: list[dict[str, Any]] = []
        by_name: dict[str, dict[str, Any]] = {}
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                raw_name = row.get("player")
                if not raw_name:
                    continue
                enriched = dict(row)
                enriched["_source"] = source_name
                enriched["_sampleSize"] = sample_size(row)
                grade_key = "grades_defense" if source_name == "defense" else "grades_offense"
                overall_grade = parse_float(row.get(grade_key))
                if overall_grade is not None:
                    enriched["overall"] = round(overall_grade, 1)
                key = normalize_name(raw_name)
                rows.append(enriched)
                existing = by_name.get(key)
                if not existing or enriched["_sampleSize"] >= existing["_sampleSize"]:
                    by_name[key] = enriched
        database["sources"][source_name] = {"rows": rows}
        for key, row in by_name.items():
            database["players"].setdefault(key, {})[source_name] = row
    return database


def csv_rating_preference(position_group: str) -> list[str]:
    if position_group == "quarterback":
        return ["passing", "rushing"]
    if position_group == "running_back":
        return ["rushing", "receiving"]
    if position_group == "receiver":
        return ["receiving", "rushing", "blocking"]
    if position_group == "offensive_line":
        return ["blocking"]
    if position_group in {"front_seven", "defensive_back"}:
        return ["defense"]
    return ["passing", "rushing", "receiving", "blocking", "defense"]


def csv_rows_for_player(player_name: str, csv_database: dict[str, Any]) -> dict[str, Any]:
    return csv_database.get("players", {}).get(normalize_name(player_name), {})


def csv_row_bucket(source_name: str, csv_position: str) -> str:
    position = (csv_position or "").upper()
    if source_name == "passing":
        return "QB"
    if source_name == "rushing":
        if "QB" in position:
            return "QB"
        if position in {"HB", "RB"}:
            return "RB"
        return "SKILL"
    if source_name == "receiving":
        if "TE" in position:
            return "TE"
        if position in {"HB", "RB"}:
            return "RB"
        return "WR"
    if source_name == "blocking":
        if position in {"T", "G", "C", "OT", "OG", "OL"}:
            return "OL"
        if "TE" in position:
            return "TE"
        return "SKILL"
    if source_name == "defense":
        if position in {"CB", "S", "DB", "NB"}:
            return "DB"
        if "LB" in position:
            return "LB"
        return "DL"
    return "ALL"


def player_metric_bucket(source_name: str, position: str, position_group: str) -> str:
    if source_name == "passing":
        return "QB"
    if source_name == "rushing":
        if position_group == "quarterback":
            return "QB"
        if position_group == "running_back":
            return "RB"
        return "SKILL"
    if source_name == "receiving":
        if position == "TE":
            return "TE"
        if position_group == "running_back":
            return "RB"
        return "WR"
    if source_name == "blocking":
        if position_group == "offensive_line":
            return "OL"
        if position == "TE":
            return "TE"
        return "SKILL"
    if source_name == "defense":
        if position_group == "defensive_back":
            return "DB"
        if position in {"WLB", "MLB"}:
            return "LB"
        return "DL"
    return "ALL"


def select_rating(
    player_name: str, position: str, position_group: str, fallback_rating: float, csv_database: dict[str, Any]
) -> tuple[float | None, dict[str, Any]]:
    records = csv_rows_for_player(player_name, csv_database)
    for source_name in csv_rating_preference(position_group):
        record = records.get(source_name)
        if record and record.get("overall") is not None:
            return record["overall"], {
                "type": "csv",
                "source": source_name,
                "team": record.get("team_name"),
                "bucket": player_metric_bucket(source_name, position, position_group),
            }
    if records:
        source_name, record = next(iter(records.items()))
        if record.get("overall") is not None:
            return record["overall"], {
                "type": "csv",
                "source": source_name,
                "team": record.get("team_name"),
                "bucket": player_metric_bucket(source_name, position, position_group),
            }
    return None, {"type": "missing", "source": "csv"}


def metric_configs(position: str, position_group: str) -> list[dict[str, Any]]:
    if position_group == "quarterback":
        return [
            {"source": "passing", "field": "grades_offense", "label": "Off Grade", "format": "grade"},
            {"source": "passing", "field": "grades_pass", "label": "Pass Grade", "format": "grade"},
            {"source": "passing", "field": "accuracy_percent", "label": "Accuracy", "format": "percent"},
            {"source": "passing", "field": "qb_rating", "label": "QB Rating", "format": "number"},
            {"source": "passing", "field": "btt_rate", "label": "BTT Rate", "format": "percent"},
            {"source": "passing", "field": "twp_rate", "label": "TWP Rate", "format": "percent", "descending": False},
            {"source": "rushing", "field": "grades_run", "label": "Run Grade", "format": "grade"},
            {"source": "rushing", "field": "scramble_yards", "label": "Scramble Yds", "format": "whole"},
        ]
    if position_group == "running_back":
        return [
            {"source": "rushing", "field": "grades_offense", "label": "Off Grade", "format": "grade"},
            {"source": "rushing", "field": "grades_run", "label": "Rush Grade", "format": "grade"},
            {"source": "rushing", "field": "elusive_rating", "label": "Elusive", "format": "number"},
            {"source": "rushing", "field": "breakaway_percent", "label": "Breakaway", "format": "percent"},
            {"source": "rushing", "field": "yco_attempt", "label": "YCO/Att", "format": "number"},
            {"source": "rushing", "field": "ypa", "label": "Yards/Att", "format": "number"},
            {"source": "receiving", "field": "grades_pass_route", "label": "Route Grade", "format": "grade"},
            {"source": "receiving", "field": "yprr", "label": "YPRR", "format": "number"},
        ]
    if position == "TE":
        return [
            {"source": "receiving", "field": "grades_offense", "label": "Off Grade", "format": "grade"},
            {"source": "receiving", "field": "grades_pass_route", "label": "Route Grade", "format": "grade"},
            {"source": "receiving", "field": "caught_percent", "label": "Catch Rate", "format": "percent"},
            {"source": "receiving", "field": "yprr", "label": "YPRR", "format": "number"},
            {"source": "receiving", "field": "yards_after_catch_per_reception", "label": "YAC/Rec", "format": "number"},
            {"source": "receiving", "field": "contested_catch_rate", "label": "Contested", "format": "percent"},
            {"source": "blocking", "field": "grades_pass_block", "label": "Pass Block", "format": "grade"},
            {"source": "blocking", "field": "grades_run_block", "label": "Run Block", "format": "grade"},
        ]
    if position_group == "receiver":
        return [
            {"source": "receiving", "field": "grades_offense", "label": "Off Grade", "format": "grade"},
            {"source": "receiving", "field": "grades_pass_route", "label": "Route Grade", "format": "grade"},
            {"source": "receiving", "field": "caught_percent", "label": "Catch Rate", "format": "percent"},
            {"source": "receiving", "field": "yprr", "label": "YPRR", "format": "number"},
            {"source": "receiving", "field": "avg_depth_of_target", "label": "aDOT", "format": "number"},
            {"source": "receiving", "field": "yards_after_catch_per_reception", "label": "YAC/Rec", "format": "number"},
            {"source": "receiving", "field": "drop_rate", "label": "Drop Rate", "format": "percent", "descending": False},
            {"source": "receiving", "field": "contested_catch_rate", "label": "Contested", "format": "percent"},
        ]
    if position_group == "offensive_line":
        return [
            {"source": "blocking", "field": "grades_offense", "label": "Off Grade", "format": "grade"},
            {"source": "blocking", "field": "grades_pass_block", "label": "Pass Block", "format": "grade"},
            {"source": "blocking", "field": "grades_run_block", "label": "Run Block", "format": "grade"},
            {"source": "blocking", "field": "pbe", "label": "PBE", "format": "number"},
            {"source": "blocking", "field": "pressures_allowed", "label": "Pressures", "format": "whole", "descending": False},
            {"source": "blocking", "field": "sacks_allowed", "label": "Sacks Allowed", "format": "whole", "descending": False},
            {"source": "blocking", "field": "hits_allowed", "label": "Hits Allowed", "format": "whole", "descending": False},
            {"source": "blocking", "field": "hurries_allowed", "label": "Hurries", "format": "whole", "descending": False},
        ]
    if position_group == "defensive_back":
        return [
            {"source": "defense", "field": "grades_defense", "label": "Defense Grade", "format": "grade"},
            {"source": "defense", "field": "grades_coverage_defense", "label": "Coverage", "format": "grade"},
            {"source": "defense", "field": "grades_tackle", "label": "Tackle", "format": "grade"},
            {"source": "defense", "field": "catch_rate", "label": "Catch Rate", "format": "percent", "descending": False},
            {"source": "defense", "field": "qb_rating_against", "label": "QB Rating Ag.", "format": "number", "descending": False},
            {"source": "defense", "field": "pass_break_ups", "label": "PBUs", "format": "whole"},
            {"source": "defense", "field": "interceptions", "label": "INTs", "format": "whole"},
            {"source": "defense", "field": "missed_tackle_rate", "label": "Missed Tk%", "format": "percent", "descending": False},
        ]
    if position in {"WLB", "MLB"}:
        return [
            {"source": "defense", "field": "grades_defense", "label": "Defense Grade", "format": "grade"},
            {"source": "defense", "field": "grades_run_defense", "label": "Run Defense", "format": "grade"},
            {"source": "defense", "field": "grades_tackle", "label": "Tackle", "format": "grade"},
            {"source": "defense", "field": "grades_coverage_defense", "label": "Coverage", "format": "grade"},
            {"source": "defense", "field": "stops", "label": "Stops", "format": "whole"},
            {"source": "defense", "field": "tackles_for_loss", "label": "TFL", "format": "whole"},
            {"source": "defense", "field": "total_pressures", "label": "Pressures", "format": "whole"},
            {"source": "defense", "field": "sacks", "label": "Sacks", "format": "whole"},
        ]
    return [
        {"source": "defense", "field": "grades_defense", "label": "Defense Grade", "format": "grade"},
        {"source": "defense", "field": "grades_pass_rush_defense", "label": "Pass Rush", "format": "grade"},
        {"source": "defense", "field": "grades_run_defense", "label": "Run Defense", "format": "grade"},
        {"source": "defense", "field": "grades_tackle", "label": "Tackle", "format": "grade"},
        {"source": "defense", "field": "total_pressures", "label": "Pressures", "format": "whole"},
        {"source": "defense", "field": "sacks", "label": "Sacks", "format": "whole"},
        {"source": "defense", "field": "tackles_for_loss", "label": "TFL", "format": "whole"},
        {"source": "defense", "field": "stops", "label": "Stops", "format": "whole"},
    ]


def format_metric_value(value: Any, kind: str) -> str:
    numeric = parse_float(value)
    if numeric is None:
        return str(value)
    if kind == "whole":
        return str(int(round(numeric)))
    if kind == "percent":
        return f"{numeric:.1f}%"
    return f"{numeric:.1f}"


def metric_rank(
    csv_database: dict[str, Any],
    source_name: str,
    field: str,
    row: dict[str, Any],
    bucket: str,
    descending: bool,
) -> tuple[int, int] | None:
    value = parse_float(row.get(field))
    if value is None:
        return None
    rows = csv_database.get("sources", {}).get(source_name, {}).get("rows", [])
    pool = [
        parse_float(candidate.get(field))
        for candidate in rows
        if parse_float(candidate.get(field)) is not None
        and csv_row_bucket(source_name, candidate.get("position", "")) == bucket
    ]
    if not pool:
        return None
    better = sum(1 for candidate in pool if candidate > value) if descending else sum(1 for candidate in pool if candidate < value)
    return better + 1, len(pool)


def build_metric_cards(
    player_name: str, position: str, position_group: str, csv_database: dict[str, Any]
) -> list[dict[str, str]]:
    records = csv_rows_for_player(player_name, csv_database)
    cards: list[dict[str, str]] = []
    for config in metric_configs(position, position_group):
        row = records.get(config["source"])
        if not row:
            continue
        value = row.get(config["field"])
        if value in ("", None):
            continue
        bucket = player_metric_bucket(config["source"], position, position_group)
        ranking = metric_rank(
            csv_database,
            config["source"],
            config["field"],
            row,
            bucket,
            config.get("descending", True),
        )
        detail_parts: list[str] = []
        if ranking:
            detail_parts.append(f"Nat. #{ranking[0]}")
        team_name = row.get("team_name")
        if team_name and team_name != "TEXAS A&M":
            detail_parts.append(team_name)
        cards.append(
            {
                "label": config["label"],
                "value": format_metric_value(value, config["format"]),
                "detail": " • ".join(detail_parts),
            }
        )
    return cards[:8]


def compute_badges(player: dict[str, Any], csv_database: dict[str, Any]) -> list[str]:
    records = csv_rows_for_player(player["name"], csv_database)
    group = player.get("positionGroup", "general")
    position = player.get("position")
    badges: list[str] = []

    def value(source_name: str, field: str) -> float | None:
        row = records.get(source_name)
        return parse_float(row.get(field)) if row else None

    if group == "quarterback":
        if (value("passing", "btt_rate") or 0) >= 4:
            badges.append("Shot Creator")
        if (value("passing", "accuracy_percent") or 0) >= 70:
            badges.append("Accurate")
        if (value("passing", "twp_rate") or 100) <= 3.5:
            badges.append("Ball Security")
        if (value("rushing", "grades_run") or 0) >= 70:
            badges.append("Run Threat")
    elif group == "running_back":
        if (value("rushing", "breakaway_percent") or 0) >= 35:
            badges.append("Home Run")
        if (value("rushing", "elusive_rating") or 0) >= 80:
            badges.append("Elusive")
        if (value("rushing", "yco_attempt") or 0) >= 3:
            badges.append("Contact Balance")
        if (value("receiving", "grades_pass_route") or 0) >= 65:
            badges.append("Receiving Value")
    elif position == "TE":
        if (value("receiving", "grades_pass_route") or 0) >= 70:
            badges.append("Route Detail")
        if (value("receiving", "yards_after_catch_per_reception") or 0) >= 6:
            badges.append("YAC Threat")
        if (value("blocking", "grades_run_block") or 0) >= 68:
            badges.append("Edge Setter")
        if (value("receiving", "caught_percent") or 0) >= 70:
            badges.append("Reliable Hands")
    elif group == "receiver":
        if (value("receiving", "grades_pass_route") or 0) >= 75:
            badges.append("Route Winner")
        if (value("receiving", "yards_after_catch_per_reception") or 0) >= 6:
            badges.append("YAC Threat")
        if (value("receiving", "avg_depth_of_target") or 0) >= 12:
            badges.append("Vertical Target")
        if (value("receiving", "caught_percent") or 0) >= 70:
            badges.append("Reliable Hands")
    elif group == "offensive_line":
        if (value("blocking", "grades_pass_block") or 0) >= 75:
            badges.append("Pass Pro")
        if (value("blocking", "grades_run_block") or 0) >= 68:
            badges.append("Run Mover")
        if (value("blocking", "pressures_allowed") or 99) <= 12:
            badges.append("Clean Pocket")
    elif group == "defensive_back":
        if (value("defense", "grades_coverage_defense") or 0) >= 70:
            badges.append("Coverage")
        if (value("defense", "interceptions") or 0) >= 2 or (value("defense", "pass_break_ups") or 0) >= 5:
            badges.append("Ball Skills")
        if (value("defense", "qb_rating_against") or 999) <= 80:
            badges.append("Lockdown")
        if (value("defense", "grades_tackle") or 0) >= 70:
            badges.append("Support Tackler")
    else:
        if (value("defense", "grades_pass_rush_defense") or 0) >= 75:
            badges.append("Pass Rush")
        if (value("defense", "grades_run_defense") or 0) >= 70:
            badges.append("Run Stopper")
        if (value("defense", "grades_tackle") or 0) >= 70:
            badges.append("Sure Tackler")
        if position in {"WLB", "MLB"} and (value("defense", "grades_coverage_defense") or 0) >= 70:
            badges.append("Coverage")

    overall = None
    for source_name in csv_rating_preference(group):
        overall = value(source_name, "grades_defense" if source_name == "defense" else "grades_offense")
        if overall is not None:
            break
    if not records:
        return ["No 2025 CSV"]

    if not badges:
        if (overall or 0) >= 80:
            badges.append("Difference Maker")
        elif (overall or 0) >= 70:
            badges.append("Reliable")
        else:
            badges.append("Rotation Value")

    return badges[:3]


def parse_cfbstats_style_summary(season: int) -> dict[str, Any]:
    html = fetch_text(CFBSTATS_TEAM_URL.format(season=season))
    soup = BeautifulSoup(html, "html.parser")
    stats: dict[str, tuple[str, str]] = {}
    for row in soup.select("tr"):
        cells = [trim_text(cell.get_text(" ", strip=True)) for cell in row.select("td")]
        if len(cells) == 3 and cells[0]:
            stats[cells[0]] = (cells[1], cells[2])

    rush_key = next((key for key in stats if key.startswith("Rushing:") and "Attempts - Yards - TD" in key), "")
    pass_key = next(
        (key for key in stats if key.startswith("Passing:") and "Attempts - Completions - Interceptions - TD" in key),
        "",
    )

    rush_for = stats.get(rush_key, ("0 - 0 - 0", "0 - 0 - 0"))[0]
    pass_for = stats.get(pass_key, ("0 - 0 - 0 - 0", "0 - 0 - 0 - 0"))[0]
    rush_against = stats.get(rush_key, ("0 - 0 - 0", "0 - 0 - 0"))[1]
    pass_against = stats.get(pass_key, ("0 - 0 - 0 - 0", "0 - 0 - 0 - 0"))[1]

    offense_rush_attempts = int(rush_for.split(" - ")[0])
    offense_pass_attempts = int(pass_for.split(" - ")[0])
    defense_rush_attempts = int(rush_against.split(" - ")[0])
    defense_pass_attempts = int(pass_against.split(" - ")[0])

    def ratio_pair(run_attempts: int, pass_attempts: int) -> dict[str, int]:
        total = max(run_attempts + pass_attempts, 1)
        run_pct = round(run_attempts * 100 / total)
        return {"run": run_pct, "pass": 100 - run_pct}

    return {
        "season": season,
        "offense": ratio_pair(offense_rush_attempts, offense_pass_attempts),
        "defense": ratio_pair(defense_rush_attempts, defense_pass_attempts),
        "source": {"label": "CFB Stats team totals", "url": CFBSTATS_TEAM_URL.format(season=season)},
    }


def formation_labels(offense_rows: list[dict[str, Any]], defense_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    offense_positions = {row["position"] for row in offense_rows}
    wr_count = sum(1 for position in offense_positions if position.startswith("WR"))
    te_count = 1 if "TE" in offense_positions else 0
    rb_count = 1 if "RB" in offense_positions else 0
    offense_personnel = f"{rb_count}{te_count} personnel"

    defensive_db = sum(1 for row in defense_rows if row["position"] in {"LCB", "RCB", "NB", "SS", "FS"})
    defensive_lb = sum(1 for row in defense_rows if row["position"] in {"WLB", "MLB"})
    defensive_dl = sum(1 for row in defense_rows if row["position"] in {"LDE", "NT", "DT", "RDE"})
    defensive_front = f"{defensive_dl}-{defensive_lb}-{defensive_db}"
    defensive_label = f"{defensive_front} nickel" if defensive_db == 5 else defensive_front

    return {
        "offense": {"label": offense_personnel, "percent": 100},
        "defense": {"label": defensive_label, "percent": 100},
    }


def compute_rating(player: dict[str, Any], depth_index: int) -> float:
    stats = player.get("stats", {}).get("statGroups", {})
    group = player.get("positionGroup", "general")
    experience = year_score(player.get("eligibility", ""))
    base_by_group = {
        "quarterback": [83, 74, 68],
        "running_back": [81, 73, 67],
        "receiver": [80, 72, 66],
        "offensive_line": [79, 72, 67],
        "front_seven": [80, 73, 67],
        "defensive_back": [80, 73, 67],
        "general": [76, 70, 65],
    }
    base = base_by_group.get(group, base_by_group["general"])[depth_index]
    score = base + experience * 4.5

    if group == "quarterback":
        score += (
            clamp((numeric_stat(stats, "passing", "QBRating") - 125) / 4.5, 0, 6)
            + clamp((numeric_stat(stats, "passing", "yardsPerPassAttempt") - 7) / 0.28, 0, 5)
            + clamp((numeric_stat(stats, "passing", "completionPct") - 58) / 2.1, 0, 3)
            + clamp((numeric_stat(stats, "passing", "passingTouchdowns") - 10) / 3.5, 0, 4)
            + clamp((numeric_stat(stats, "rushing", "rushingYards") - 150) / 100, 0, 3)
            - clamp(numeric_stat(stats, "passing", "interceptions") / 3, 0, 3)
        )
    elif group == "running_back":
        score += (
            clamp((numeric_stat(stats, "rushing", "yardsPerRushAttempt") - 4.2) / 0.25, 0, 6)
            + clamp((numeric_stat(stats, "rushing", "rushingYards") - 300) / 125, 0, 6)
            + clamp((numeric_stat(stats, "rushing", "rushingTouchdowns") - 3) / 1.5, 0, 4)
            + clamp((numeric_stat(stats, "receiving", "receptions") - 10) / 6, 0, 2)
        )
    elif group == "receiver":
        score += (
            clamp((numeric_stat(stats, "receiving", "receivingYards") - 250) / 110, 0, 6)
            + clamp((numeric_stat(stats, "receiving", "receptions") - 20) / 7, 0, 4)
            + clamp((numeric_stat(stats, "receiving", "yardsPerReception") - 11) / 0.65, 0, 4)
            + clamp((numeric_stat(stats, "receiving", "receivingTouchdowns") - 2) / 1.3, 0, 3)
        )
    elif group == "offensive_line":
        weight = player.get("weightPounds") or 300
        score += clamp((weight - 290) / 8, 0, 3)
    elif group == "front_seven":
        score += (
            clamp((numeric_stat(stats, "defensive", "totalTackles") - 25) / 8, 0, 4)
            + clamp((numeric_stat(stats, "defensive", "tacklesForLoss") - 3) / 1.5, 0, 5)
            + clamp((numeric_stat(stats, "defensive", "sacks") - 1.5) / 0.8, 0, 5)
            + clamp((numeric_stat(stats, "defensive", "forcedFumbles")) * 1.8, 0, 3)
        )
    elif group == "defensive_back":
        score += (
            clamp((numeric_stat(stats, "defensive", "interceptions")) * 2.5, 0, 5)
            + clamp((numeric_stat(stats, "defensive", "passesDefensed") - 2) / 1.1, 0, 5)
            + clamp((numeric_stat(stats, "defensive", "totalTackles") - 20) / 10, 0, 3)
            + clamp((numeric_stat(stats, "defensive", "forcedFumbles")) * 1.6, 0, 2)
        )

    return round(clamp(score, 60, 93), 1)


def build_highlight_link(player_name: str) -> dict[str, str]:
    query = f"{player_name} Texas A&M football highlights"
    return {
        "label": "Search highlights",
        "url": f"https://www.youtube.com/results?search_query={quote_plus(query)}",
    }


def merge_player(
    raw_player: dict[str, Any],
    position: str,
    depth_index: int,
    roster_map: dict[str, Any],
    stats_map: dict[str, Any],
    twelfthman_links: dict[str, str],
    person_cache: dict[str, Any],
    csv_database: dict[str, Any],
) -> dict[str, Any]:
    normalized = normalize_name(raw_player["name"])
    roster = roster_map.get(normalized, {})
    stats = stats_map.get(normalized, {})
    twelfthman_url = twelfthman_links.get(normalized)

    twelfthman = {}
    if twelfthman_url:
        if twelfthman_url not in person_cache:
            person_cache[twelfthman_url] = parse_12thman_person(twelfthman_url)
        twelfthman = person_cache[twelfthman_url]

    position_group = guess_position_group(position)
    player = {
        "id": roster.get("espnId") or slugify(raw_player["name"]),
        "name": roster.get("name") or raw_player["name"],
        "position": position,
        "positionGroup": position_group,
        "depthIndex": depth_index,
        "depthLabel": ["Starter", "2nd String", "3rd String"][depth_index],
        "eligibility": raw_player.get("eligibility") or "",
        "jersey": raw_player.get("jersey") or roster.get("jersey"),
        "height": twelfthman.get("fields", {}).get("Height") or roster.get("height"),
        "weight": twelfthman.get("fields", {}).get("Weight") or roster.get("weight"),
        "heightInches": roster.get("heightInches"),
        "weightPounds": roster.get("weightPounds"),
        "class": twelfthman.get("fields", {}).get("Class") or roster.get("collegeClass"),
        "hometown": twelfthman.get("fields", {}).get("Hometown"),
        "highSchool": twelfthman.get("fields", {}).get("High School"),
        "headshot": twelfthman.get("headshot") or roster.get("headshot") or stats.get("headshot"),
        "bio": twelfthman.get("bio") or "",
        "bioShort": twelfthman.get("bioShort") or twelfthman.get("bio") or "",
        "bioSource": twelfthman.get("sourceUrl"),
        "espnPlayerUrl": roster.get("espnPlayerUrl") or stats.get("espnPlayerUrl"),
        "stats": stats,
        "highlight": build_highlight_link(roster.get("name") or raw_player["name"]),
        "sourceLinks": [
            {"label": "Ourlads depth slot", "url": raw_player.get("sourceUrl")},
            *(
                [{"label": "12thMan bio", "url": twelfthman.get("sourceUrl")}]
                if twelfthman.get("sourceUrl")
                else []
            ),
            *(
                [{"label": "ESPN player page", "url": roster.get("espnPlayerUrl") or stats.get("espnPlayerUrl")}]
                if roster.get("espnPlayerUrl") or stats.get("espnPlayerUrl")
                else []
            ),
        ],
    }
    fallback_rating = compute_rating(player, depth_index)
    player["rating"], player["ratingSource"] = select_rating(
        player["name"], position, position_group, fallback_rating, csv_database
    )
    player["badges"] = compute_badges(player, csv_database)
    player["metricCards"] = build_metric_cards(player["name"], position, position_group, csv_database)
    return player


def format_row(
    row: dict[str, Any],
    roster_map: dict[str, Any],
    stats_map: dict[str, Any],
    twelfthman_links: dict[str, str],
    person_cache: dict[str, Any],
    csv_database: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    players = []
    lineup = {"position": row["position"], "playerIds": []}
    for depth_index, raw_player in enumerate(row["players"][:3]):
        merged = merge_player(
            raw_player,
            row["position"],
            depth_index,
            roster_map,
            stats_map,
            twelfthman_links,
            person_cache,
            csv_database,
        )
        players.append(merged)
        lineup["playerIds"].append(merged["id"])
    return lineup, players


def gather_coaches(person_cache: dict[str, Any]) -> dict[str, Any]:
    coaches: dict[str, Any] = {}
    for name, url in COACH_URLS.items():
        if url not in person_cache:
            person_cache[url] = parse_12thman_person(url)
        person = person_cache[url]
        meta = COACH_TENDENCIES[name]
        coaches[slugify(name)] = {
            "name": name,
            "role": meta["role"],
            "headshot": person.get("headshot"),
            "bio": person.get("bioShort") or person.get("bio"),
            "bioShort": person.get("bioShort") or person.get("bio"),
            "bioSource": url,
            "tendencies": meta["tendencies"],
            "tendencySources": meta["sources"],
        }
    return coaches


def build_payload() -> dict[str, Any]:
    person_cache: dict[str, Any] = {}
    csv_database = load_csv_database()

    depth = parse_ourlads_depth(fetch_text(OURLADS_SECURE_DEPTH_URL), fetch_text(OURLADS_DEPTH_URL))
    roster_data = parse_espn_roster()
    stats_data = parse_espn_team_stats(fetch_text(ESPN_TEAM_STATS_URL))
    twelfthman_links = parse_12thman_roster_index(fetch_text(TWELFTHMAN_ROSTER_URL))

    roster_map = roster_data["athletes"]
    stats_map = stats_data["players"]

    players: dict[str, Any] = {}
    offense_rows: list[dict[str, Any]] = []
    defense_rows: list[dict[str, Any]] = []

    for row in depth["offense"]:
        lineup, row_players = format_row(
            row, roster_map, stats_map, twelfthman_links, person_cache, csv_database
        )
        offense_rows.append(lineup)
        for player in row_players:
            players[str(player["id"])] = player

    for row in depth["defense"]:
        lineup, row_players = format_row(
            row, roster_map, stats_map, twelfthman_links, person_cache, csv_database
        )
        defense_rows.append(lineup)
        for player in row_players:
            players[str(player["id"])] = player

    coaches = gather_coaches(person_cache)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    latest_stat_season = stats_data["season"] or roster_data["season"].get("year")
    latest_stat_season_int = int(str(latest_stat_season))
    analysis_season = (
        latest_stat_season_int - 1
        if (roster_data["season"].get("name") or "").lower() == "preseason"
        else latest_stat_season_int
    )
    style_totals = parse_cfbstats_style_summary(analysis_season)
    formation_summary = formation_labels(depth["offense"], depth["defense"])

    return {
        "team": {
            "name": TEAM_NAME,
            "shortName": "Texas A&M",
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/245.png",
            "colors": {"primary": "#500000", "secondary": "#9e7f5a", "accent": "#f7f0e8"},
        },
        "generatedAt": now,
        "latestStatSeason": str(latest_stat_season),
        "seasonContext": {
            "rosterSeason": roster_data["season"].get("year"),
            "rosterPhase": roster_data["season"].get("name") or roster_data["season"].get("displayName"),
            "note": (
                "Roster is currently in preseason mode, so ESPN may still surface the latest available production while current-season game stats accumulate."
                if (roster_data["season"].get("name") or "").lower() == "preseason"
                else "Displaying current season player stats."
            ),
        },
        "depthChart": {
            "updatedAt": depth["updatedAt"],
            "offense": offense_rows,
            "defense": defense_rows,
            "layouts": {"offense": OFFENSE_LAYOUT, "defense": DEFENSE_LAYOUT},
            "styleSummary": {
                "offense": {
                    "formation": formation_summary["offense"],
                    "runPass": style_totals["offense"],
                    "season": analysis_season,
                },
                "defense": {
                    "formation": formation_summary["defense"],
                    "runPass": style_totals["defense"],
                    "season": analysis_season,
                },
            },
        },
        "players": players,
        "coaches": coaches,
        "sources": [
            depth["source"],
            roster_data["source"],
            stats_data["source"],
            {"label": "12thMan roster", "url": TWELFTHMAN_ROSTER_URL},
        ],
    }


def main() -> int:
    payload = build_payload()
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
