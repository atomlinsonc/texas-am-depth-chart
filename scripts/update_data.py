#!/usr/bin/env python3

from __future__ import annotations

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
OURLADS_DEPTH_URL = "https://secure.ourlads.com/ncaa-football-depth-charts/depth-chart/texas-am/92039"
TWELFTHMAN_ROSTER_URL = "https://12thman.com/sports/football/roster"
COACH_URLS = {
    "Mike Elko": "https://12thman.com/sports/football/roster/coaches/mike-elko/2151",
    "Collin Klein": "https://12thman.com/sports/football/roster/coaches/collin-klein/2229",
    "Lyle Hemphill": "https://12thman.com/sports/football/roster/coaches/lyle-hemphill/1990",
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

OFFENSE_LAYOUT = {
    "WR-X": {"x": 12, "y": 16},
    "WR-SL": {"x": 22, "y": 35},
    "LT": {"x": 38, "y": 44},
    "LG": {"x": 44, "y": 44},
    "C": {"x": 50, "y": 44},
    "RG": {"x": 56, "y": 44},
    "RT": {"x": 62, "y": 44},
    "TE": {"x": 70, "y": 41},
    "QB": {"x": 50, "y": 58},
    "RB": {"x": 50, "y": 72},
    "WR-Z": {"x": 88, "y": 16},
}

DEFENSE_LAYOUT = {
    "LCB": {"x": 12, "y": 18},
    "NB": {"x": 27, "y": 30},
    "LDE": {"x": 36, "y": 42},
    "NT": {"x": 46, "y": 42},
    "DT": {"x": 54, "y": 42},
    "RDE": {"x": 64, "y": 42},
    "WLB": {"x": 38, "y": 58},
    "MLB": {"x": 62, "y": 58},
    "SS": {"x": 42, "y": 75},
    "FS": {"x": 58, "y": 75},
    "RCB": {"x": 88, "y": 18},
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
    "Collin Klein": {
        "role": "Offensive Coordinator",
        "tendencies": [
            "Run-game-first approach built around QB mobility, conflict keys, and forcing defenses to fit every gap.",
            "Frequent TE usage and formation variation to create leverage for both the run game and shot plays.",
            "Prefers adaptable weekly game plans rather than calling the same menu every week.",
        ],
        "sources": [
            {
                "label": "KSAT on Collin Klein's offense",
                "url": "https://www.ksat.com/news/local/2023/12/08/what-texas-am-fans-can-expect-from-a-collin-klein-led-offense-next-season/",
            },
            {
                "label": "Houston Chronicle on offensive conflict",
                "url": "https://www.houstonchronicle.com/sports/college/article/texas-aggies-offense-collin-klein-19622652.php",
            },
            {
                "label": "Official Texas A&M bio",
                "url": COACH_URLS["Collin Klein"],
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


def parse_ourlads_depth(html: str) -> dict[str, Any]:
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

    return {
        "updatedAt": updated_at,
        "offenseScheme": schemes.get("offense", ""),
        "defenseScheme": schemes.get("defense", ""),
        "offense": parse_depth_table(offense_tbody),
        "defense": parse_depth_table(defense_tbody),
        "source": {
            "label": "Ourlads depth chart",
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
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image:
        headshot = og_image.get("content")
    if not headshot:
        image = soup.find("img")
        if image:
            headshot = image.get("src")

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


def compute_rating(player: dict[str, Any], depth_index: int) -> int:
    stats = player.get("stats", {}).get("statGroups", {})
    group = player.get("positionGroup", "general")
    experience = year_score(player.get("eligibility", ""))
    role_bonus = {0: 8, 1: 3, 2: 0}.get(depth_index, 0)

    if group == "quarterback":
        score = (
            numeric_stat(stats, "passing", "QBRating") * 0.35
            + numeric_stat(stats, "passing", "completionPct") * 0.18
            + numeric_stat(stats, "passing", "yardsPerPassAttempt") * 4.0
            + numeric_stat(stats, "passing", "passingTouchdowns") * 1.2
            - numeric_stat(stats, "passing", "interceptions") * 1.8
            + numeric_stat(stats, "rushing", "yardsPerRushAttempt") * 2.2
        )
        score = 45 + score / 2.8
    elif group == "running_back":
        score = (
            numeric_stat(stats, "rushing", "yardsPerRushAttempt") * 10.5
            + numeric_stat(stats, "rushing", "rushingYards") / 36
            + numeric_stat(stats, "rushing", "rushingTouchdowns") * 1.9
            + numeric_stat(stats, "receiving", "yardsPerReception") * 1.1
        )
        score = 48 + score / 2.0
    elif group == "receiver":
        score = (
            numeric_stat(stats, "receiving", "receivingYards") / 24
            + numeric_stat(stats, "receiving", "receptions") * 0.8
            + numeric_stat(stats, "receiving", "yardsPerReception") * 3.2
            + numeric_stat(stats, "receiving", "receivingTouchdowns") * 2.4
        )
        score = 46 + score / 2.2
    elif group == "offensive_line":
        weight = player.get("weightPounds") or 300
        score = 54 + experience * 18 + clamp((weight - 280) / 5, 0, 8)
    elif group == "front_seven":
        score = (
            numeric_stat(stats, "defensive", "totalTackles") * 0.7
            + numeric_stat(stats, "defensive", "tacklesForLoss") * 3.0
            + numeric_stat(stats, "defensive", "sacks") * 4.0
            + numeric_stat(stats, "defensive", "passesDefensed") * 1.6
            + numeric_stat(stats, "defensive", "interceptions") * 4.5
        )
        score = 48 + score / 2.0
    elif group == "defensive_back":
        score = (
            numeric_stat(stats, "defensive", "interceptions") * 6.0
            + numeric_stat(stats, "defensive", "passesDefensed") * 2.4
            + numeric_stat(stats, "defensive", "totalTackles") * 0.55
            + numeric_stat(stats, "defensive", "forcedFumbles") * 4.0
        )
        score = 47 + score / 2.0
    else:
        score = 50 + experience * 14

    score += role_bonus + experience * 4
    return int(round(clamp(score, 55, 98)))


def compute_badges(player: dict[str, Any]) -> list[str]:
    stats = player.get("stats", {}).get("statGroups", {})
    group = player.get("positionGroup", "general")
    badges: list[str] = []

    if group == "quarterback":
        if numeric_stat(stats, "rushing", "rushingYards") >= 250 or numeric_stat(stats, "rushing", "yardsPerRushAttempt") >= 4.5:
            badges.append("Dual Threat")
        if numeric_stat(stats, "passing", "yardsPerPassAttempt") >= 8:
            badges.append("Explosive Arm")
        if not badges:
            badges.append("Field General")
    elif group == "running_back":
        if numeric_stat(stats, "rushing", "yardsPerRushAttempt") >= 5:
            badges.append("Burst")
        if numeric_stat(stats, "rushing", "rushingTouchdowns") >= 6:
            badges.append("Red Zone")
        if not badges:
            badges.append("Ball Carrier")
    elif group == "receiver":
        if numeric_stat(stats, "receiving", "yardsPerReception") >= 14:
            badges.append("Explosive")
        if numeric_stat(stats, "receiving", "receivingTouchdowns") >= 5:
            badges.append("Finisher")
        if numeric_stat(stats, "receiving", "receptions") >= 35:
            badges.append("Chain Mover")
        if not badges:
            badges.append("Target")
    elif group == "offensive_line":
        badges.extend(["Anchor", "Pass Pro"])
    elif group == "front_seven":
        if numeric_stat(stats, "defensive", "sacks") >= 4:
            badges.append("Pressure")
        if numeric_stat(stats, "defensive", "tacklesForLoss") >= 6:
            badges.append("Backfield Hunter")
        if not badges:
            badges.append("Run Stopper")
    elif group == "defensive_back":
        if numeric_stat(stats, "defensive", "interceptions") >= 2:
            badges.append("Ball Hawk")
        if numeric_stat(stats, "defensive", "passesDefensed") >= 4:
            badges.append("Coverage")
        if not badges:
            badges.append("Tackler")
    else:
        badges.append("Contributor")

    if player.get("eligibility", "").upper().startswith("FR"):
        badges.append("Upside")

    return badges[:3]


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

    player = {
        "id": roster.get("espnId") or slugify(raw_player["name"]),
        "name": roster.get("name") or raw_player["name"],
        "position": position,
        "positionGroup": guess_position_group(position),
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
        "bio": twelfthman.get("bioShort") or "",
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
    player["rating"] = compute_rating(player, depth_index)
    player["badges"] = compute_badges(player)
    return player


def format_row(
    row: dict[str, Any],
    roster_map: dict[str, Any],
    stats_map: dict[str, Any],
    twelfthman_links: dict[str, str],
    person_cache: dict[str, Any],
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
            "bioSource": url,
            "tendencies": meta["tendencies"],
            "tendencySources": meta["sources"],
        }
    return coaches


def build_payload() -> dict[str, Any]:
    person_cache: dict[str, Any] = {}

    depth = parse_ourlads_depth(fetch_text(OURLADS_DEPTH_URL))
    roster_data = parse_espn_roster()
    stats_data = parse_espn_team_stats(fetch_text(ESPN_TEAM_STATS_URL))
    twelfthman_links = parse_12thman_roster_index(fetch_text(TWELFTHMAN_ROSTER_URL))

    roster_map = roster_data["athletes"]
    stats_map = stats_data["players"]

    players: dict[str, Any] = {}
    offense_rows: list[dict[str, Any]] = []
    defense_rows: list[dict[str, Any]] = []

    for row in depth["offense"]:
        lineup, row_players = format_row(row, roster_map, stats_map, twelfthman_links, person_cache)
        offense_rows.append(lineup)
        for player in row_players:
            players[str(player["id"])] = player

    for row in depth["defense"]:
        lineup, row_players = format_row(row, roster_map, stats_map, twelfthman_links, person_cache)
        defense_rows.append(lineup)
        for player in row_players:
            players[str(player["id"])] = player

    coaches = gather_coaches(person_cache)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    latest_stat_season = stats_data["season"] or roster_data["season"].get("year")

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
            "offenseScheme": depth["offenseScheme"],
            "defenseScheme": depth["defenseScheme"],
            "offense": offense_rows,
            "defense": defense_rows,
            "layouts": {"offense": OFFENSE_LAYOUT, "defense": DEFENSE_LAYOUT},
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
