from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
import re
import shutil
import time
import unicodedata
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, unquote, urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parent.parent
RECONCILIATION_PATH = REPO_ROOT / "data" / "visual_assets" / "wc_pipeline" / "wc_reconciliation_map.json"
STAGING_DIR = REPO_ROOT / "artifacts" / "staging" / "world-cup-player-assets"
PUBLISHED_DIR = REPO_ROOT / "data" / "visual_assets" / "wc_overlay" / "players"
MANIFEST_PATH = REPO_ROOT / "data" / "visual_assets" / "wc_pipeline" / "wc_player_asset_manifest.json"
REQUEST_TIMEOUT_SECONDS = 12
MAX_IMAGE_DIMENSION = 1200
USER_AGENT = "football-analytics/1.0 (world-cup-player-assets)"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
WIKIPEDIA_PAGE_URL = "https://en.wikipedia.org/wiki/"
WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/index.php"
PUBLISHED_THRESHOLD = 0.88
PENDING_REVIEW_THRESHOLD = 0.7
SEARCH_RESULT_LIMIT = 3
REQUEST_THROTTLE_SECONDS = 0.15
FOOTBALL_TERMS = (
    "football",
    "footballer",
    "footballers",
    "soccer",
    "striker",
    "midfielder",
    "goalkeeper",
    "defender",
    "forward",
    "winger",
    "sweeper",
    "international",
)
WRONG_SPORT_TERMS = (
    "american football",
    "australian rules",
    "baseball",
    "basketball",
    "boxer",
    "boxing",
    "cricketer",
    "cyclist",
    "gaelic football",
    "gridiron",
    "handball",
    "ice hockey",
    "mixed martial artist",
    "rugby",
    "sprinter",
    "swimmer",
    "tennis",
    "victorian football league",
    "volleyball",
    "wrestler",
)
NEGATIVE_TERMS = (
    "album",
    "actor",
    "actress",
    "artist",
    "band",
    "book",
    "composer",
    "film",
    "magazine",
    "municipality",
    "politician",
    "racehorse",
    "settlement",
    "village",
)
NAME_PARTICLES = {
    "da",
    "de",
    "del",
    "di",
    "do",
    "dos",
    "du",
    "la",
    "le",
    "van",
    "von",
}
GENERIC_CONTEXT_TOKENS = {"and", "cup", "of", "the", "world"}
INFOBOX_FOOTBALL_TERMS = (
    "association football",
    "footballer",
    "national team",
    "playing position",
    "senior career",
    "soccer player",
    "youth career",
)
DEFAULT_STATUS_BY_DECISION = {
    "NEEDS_REVIEW": "pending_review",
    "NO_MATCH": "rejected",
    "UNRESOLVABLE": "unresolvable",
}
TRACKED_STATUSES = ("published", "pending_review", "rejected", "unresolvable")
BIRTH_DATE_KEYS = ("birth_date", "date_of_birth", "dob")
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/"
COMMONS_FILE_PATH_URL = "https://commons.wikimedia.org/wiki/Special:FilePath/"
SITELINK_IMAGE_SITES = (
    "dewiki",
    "frwiki",
    "eswiki",
    "itwiki",
    "ptwiki",
    "nlwiki",
    "plwiki",
    "cswiki",
    "svwiki",
    "trwiki",
    "rowiki",
    "huwiki",
)
PLACEHOLDER_IMAGE_TERMS = (
    "defaut",
    "default",
    "flag_of_",
    "football_pictogram",
    "icon",
    "no_image",
    "replace_this_image",
    "soccerball",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Busca/stageia/publica assets de jogadores da Copa por wc_player_id, "
            "preservando published e reprocessando apenas os buckets desejados."
        )
    )
    parser.add_argument(
        "--only-status",
        nargs="+",
        choices=("rejected", "pending_review", "published", "unresolvable"),
        default=None,
        help="Quando um manifesto anterior existir, reprocessa apenas esses status.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_repo_relative(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.relative_to(REPO_ROOT).as_posix()


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
    lowered = ascii_text.lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def is_football_related(description: str) -> bool:
    normalized_description = normalize_text(description)
    return any(term in normalized_description for term in FOOTBALL_TERMS)


def has_negative_signal(description: str) -> bool:
    normalized_description = normalize_text(description)
    return any(term in normalized_description for term in NEGATIVE_TERMS)


def has_wrong_sport_signal(description: str) -> bool:
    normalized_description = normalize_text(description)
    return any(term in normalized_description for term in WRONG_SPORT_TERMS)


def normalize_name_for_matching(value: str) -> str:
    normalized = normalize_text(value)
    tokens = [token for token in normalized.split() if token not in NAME_PARTICLES]
    return " ".join(tokens)


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def build_name_aliases(player_name: str) -> list[str]:
    raw_tokens = [token for token in re.split(r"[\s\-–']+", player_name) if token]
    aliases = [player_name]
    ascii_name = unicodedata.normalize("NFKD", player_name)
    ascii_name = "".join(character for character in ascii_name if not unicodedata.combining(character))
    if ascii_name != player_name:
        aliases.append(ascii_name)

    if len(raw_tokens) >= 2:
        aliases.append(f"{raw_tokens[0]} {raw_tokens[-1]}")
        aliases.append(" ".join(raw_tokens[-2:]))
    if 2 <= len(raw_tokens) <= 3:
        aliases.append(" ".join(reversed(raw_tokens)))
    return unique_preserve_order(aliases)


def build_player_context(player: dict[str, object]) -> str:
    team_slug = str(player.get("team_slug") or "")
    team_display_name = str(player.get("team_display_name") or "")
    slug_context = team_slug.removeprefix("world-cup-").replace("-", " ").strip()
    return " ".join(part for part in (team_display_name, slug_context) if part).strip()


def build_query_variants(player_name: str, player: dict[str, object]) -> list[str]:
    context = build_player_context(player)
    queries: list[str] = []
    editions = [str(edition) for edition in player.get("editions") or []]
    for name_variant in build_name_aliases(player_name):
        queries.append(f'"{name_variant}" footballer')
        queries.append(f'"{name_variant}" soccer player')
        queries.append(f'"{name_variant}" FIFA World Cup')
        if context:
            queries.append(f'"{name_variant}" footballer {context}')
            queries.append(f'"{name_variant}" soccer player {context}')
            queries.append(f'"{name_variant}" {context}')
        if len(normalize_name_for_matching(name_variant).split()) == 1:
            queries.append(f'{name_variant} footballer {context}'.strip())
            queries.append(f'{name_variant} football player {context}'.strip())
        for edition in editions[:2]:
            queries.append(f'"{name_variant}" "{edition} FIFA World Cup"')
    return unique_preserve_order(queries)


def build_title_variants(player_name: str) -> list[str]:
    with_suffix = []
    for variant in build_name_aliases(player_name):
        with_suffix.append(variant)
        with_suffix.append(f"{variant} (footballer)")
    return unique_preserve_order(with_suffix)


def build_searched_aliases(player: dict[str, object]) -> list[str]:
    player_name = str(player["player_name"])
    return unique_preserve_order(build_title_variants(player_name) + build_query_variants(player_name, player))


def extract_text_tokens(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if token and token not in GENERIC_CONTEXT_TOKENS}


def extract_context_tokens(player: dict[str, object]) -> set[str]:
    team_slug = str(player.get("team_slug") or "").removeprefix("world-cup-").replace("-", " ")
    team_display_name = str(player.get("team_display_name") or "")
    tokens = extract_text_tokens(f"{team_slug} {team_display_name}")
    return {token for token in tokens if len(token) >= 3}


def count_token_prefix_matches(context_tokens: set[str], text_tokens: set[str]) -> int:
    matches = 0
    for context_token in context_tokens:
        if len(context_token) < 3:
            continue
        if any(
            len(text_token) >= 3
            and (text_token.startswith(context_token[:3]) or context_token.startswith(text_token[:3]))
            for text_token in text_tokens
        ):
            matches += 1
    return matches


def token_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def best_name_token_similarity(requested_tokens: set[str], title_tokens: set[str]) -> tuple[float, float]:
    if not requested_tokens or not title_tokens:
        return 0.0, 0.0
    best_scores = [
        max(token_similarity(requested_token, title_token) for title_token in title_tokens)
        for requested_token in requested_tokens
    ]
    return min(best_scores), sum(best_scores) / len(best_scores)


def normalize_image_url_key(url: str) -> str:
    return normalize_text(unquote(url.rsplit("/", 1)[-1]))


def is_placeholder_image_url(url: str | None) -> bool:
    if not url:
        return True
    normalized_key = normalize_image_url_key(url)
    return any(term in normalized_key for term in PLACEHOLDER_IMAGE_TERMS)


def extract_birth_year_from_text(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    if match is None:
        return None
    return int(match.group(0))


def extract_player_birth_year(player: dict[str, object]) -> int | None:
    for key in BIRTH_DATE_KEYS:
        birth_value = player.get(key)
        birth_year = extract_birth_year_from_text(str(birth_value)) if birth_value else None
        if birth_year is not None:
            return birth_year
    return None


def build_fallback_status(player: dict[str, object]) -> str:
    return DEFAULT_STATUS_BY_DECISION.get(str(player.get("decision") or ""), "rejected")


def count_manifest_statuses(manifest_entries: list[dict[str, object]]) -> dict[str, int]:
    return {
        status: sum(1 for entry in manifest_entries if entry.get("status") == status)
        for status in TRACKED_STATUSES
    }


def fetch_response(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, object] | None = None,
    allow_404: bool = False,
) -> requests.Response:
    delay_seconds = 1.0
    last_error: Exception | None = None
    for _ in range(4):
        try:
            time.sleep(REQUEST_THROTTLE_SECONDS)
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code in RETRYABLE_STATUS_CODES:
                time.sleep(delay_seconds)
                delay_seconds *= 2
                continue
            if allow_404 and response.status_code == 404:
                return response
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            time.sleep(delay_seconds)
            delay_seconds *= 2
    if last_error is None:
        raise RuntimeError(f"Unable to fetch url={url} params={params}")
    raise last_error


def fetch_bytes(session: requests.Session, url: str) -> bytes:
    delay_seconds = 1.0
    last_error: Exception | None = None
    for _ in range(5):
        try:
            time.sleep(REQUEST_THROTTLE_SECONDS)
            response = session.get(requests.utils.requote_uri(url), timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code in RETRYABLE_STATUS_CODES:
                time.sleep(delay_seconds * 2)
                delay_seconds *= 2
                continue
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            last_error = error
            time.sleep(delay_seconds)
            delay_seconds *= 2
    if last_error is None:
        raise RuntimeError(f"Unable to fetch image: {url}")
    raise last_error


def save_png(image_bytes: bytes, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(image_bytes)) as image:
        image = image.convert("RGBA")
        if max(image.size) > MAX_IMAGE_DIMENSION:
            image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
        image.save(output_path, format="PNG")


def extract_first_paragraph(soup: BeautifulSoup) -> str:
    for paragraph in soup.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if text and len(text) >= 40:
            return text
    return ""


def extract_categories(soup: BeautifulSoup) -> list[str]:
    categories = []
    for anchor in soup.select("#mw-normal-catlinks ul li a"):
        text = anchor.get_text(" ", strip=True)
        if text:
            categories.append(text)
    return categories


def extract_infobox_text(soup: BeautifulSoup) -> str:
    infobox = soup.select_one("table.infobox")
    if infobox is None:
        return ""
    return infobox.get_text(" ", strip=True)


def has_football_infobox(infobox_text: str) -> bool:
    normalized_infobox = normalize_text(infobox_text)
    return any(term in normalized_infobox for term in INFOBOX_FOOTBALL_TERMS)


def extract_preferred_thumbnail_url(soup: BeautifulSoup) -> str | None:
    infobox_image = soup.select_one("table.infobox img")
    if infobox_image:
        srcset = infobox_image.get("srcset")
        if isinstance(srcset, str) and srcset.strip():
            srcset_parts = [part.strip().split(" ", 1)[0] for part in srcset.split(",") if part.strip()]
            if srcset_parts:
                return urljoin("https:", srcset_parts[-1])
        src = infobox_image.get("src")
        if isinstance(src, str) and src.strip():
            return urljoin("https:", src)

    og_image = soup.find("meta", attrs={"property": "og:image"})
    if og_image and og_image.get("content"):
        return str(og_image["content"])
    return None


def extract_page_from_html(response: requests.Response) -> dict[str, object] | None:
    if response.status_code != 200:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    og_title = soup.find("meta", attrs={"property": "og:title"})
    title = og_title.get("content", "").replace(" - Wikipedia", "").strip() if og_title else ""
    if not title or title.endswith("Search results"):
        return None

    description = extract_first_paragraph(soup)
    categories = extract_categories(soup)
    infobox_text = extract_infobox_text(soup)
    is_disambiguation = bool(
        soup.select_one("table.ambox-disambig")
        or soup.select_one("meta[property='mw:PageProp/disambiguation']")
        or "disambiguation" in normalize_text(description)
        or any("disambiguation" in normalize_text(category) for category in categories)
    )

    return {
        "title": title,
        "description": description,
        "thumbnail_url": extract_preferred_thumbnail_url(soup),
        "page_url": response.url,
        "is_disambiguation": is_disambiguation,
        "categories": categories,
        "has_football_infobox": has_football_infobox(infobox_text),
        "infobox_text": infobox_text,
        "birth_year": extract_birth_year_from_text(f"{description} {infobox_text}"),
    }


def build_page_url(title: str) -> str:
    normalized_title = title.replace(" ", "_")
    return f"{WIKIPEDIA_PAGE_URL}{quote(normalized_title)}"


def build_generic_wikipedia_url(site_key: str, title: str) -> str:
    language = site_key.removesuffix("wiki")
    normalized_title = title.replace(" ", "_")
    return f"https://{language}.wikipedia.org/wiki/{quote(normalized_title)}"


def fetch_page_by_title(session: requests.Session, title: str) -> dict[str, object] | None:
    response = fetch_response(session, build_page_url(title), allow_404=True)
    return extract_page_from_html(response)


def fetch_page_by_url(session: requests.Session, url: str) -> dict[str, object] | None:
    response = fetch_response(session, url, allow_404=True)
    return extract_page_from_html(response)


def fetch_wikibase_item_id(session: requests.Session, title: str) -> str | None:
    response = fetch_response(
        session,
        WIKIPEDIA_API_URL,
        params={
            "action": "query",
            "titles": title,
            "prop": "pageprops",
            "format": "json",
            "redirects": 1,
        },
    )
    payload = response.json()
    pages = payload.get("query", {}).get("pages", {})
    if not pages:
        return None
    page = next(iter(pages.values()))
    pageprops = page.get("pageprops") or {}
    wikibase_item = pageprops.get("wikibase_item")
    return str(wikibase_item) if wikibase_item else None


def fetch_wikidata_entity(session: requests.Session, wikibase_item: str) -> dict[str, object] | None:
    response = fetch_response(session, f"{WIKIDATA_ENTITY_URL}{wikibase_item}.json")
    payload = response.json()
    entity = payload.get("entities", {}).get(wikibase_item)
    return entity if isinstance(entity, dict) else None


def extract_wikidata_p18_url(entity: dict[str, object]) -> str | None:
    claims = entity.get("claims") or {}
    image_claims = claims.get("P18") or []
    if not image_claims:
        return None
    image_name = image_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
    if not isinstance(image_name, str) or not image_name.strip():
        return None
    return f"{COMMONS_FILE_PATH_URL}{quote(image_name)}"


def resolve_candidate_image_url(
    session: requests.Session,
    candidate: dict[str, object],
) -> tuple[str | None, list[str]]:
    image_url = candidate.get("thumbnail_url")
    if isinstance(image_url, str) and image_url.strip() and not is_placeholder_image_url(image_url):
        return image_url, []

    page_title = str(candidate.get("title") or "").strip()
    if not page_title:
        return None, []

    wikibase_item = fetch_wikibase_item_id(session, page_title)
    if not wikibase_item:
        return None, []

    entity = fetch_wikidata_entity(session, wikibase_item)
    if not entity:
        return None, []

    p18_url = extract_wikidata_p18_url(entity)
    if p18_url and not is_placeholder_image_url(p18_url):
        return p18_url, ["wikidata_p18_image"]

    sitelinks = entity.get("sitelinks") or {}
    for site_key in SITELINK_IMAGE_SITES:
        sitelink = sitelinks.get(site_key)
        if not isinstance(sitelink, dict):
            continue
        site_title = sitelink.get("title")
        if not isinstance(site_title, str) or not site_title.strip():
            continue
        site_page = fetch_page_by_url(session, build_generic_wikipedia_url(site_key, site_title))
        if site_page is None:
            continue
        site_image_url = site_page.get("thumbnail_url")
        if isinstance(site_image_url, str) and site_image_url.strip() and not is_placeholder_image_url(site_image_url):
            return site_image_url, [f"crosswiki_infobox_image:{site_key}"]

    return None, []


def search_candidate_titles(session: requests.Session, player_name: str, player: dict[str, object]) -> list[str]:
    titles: list[str] = []
    for query in build_query_variants(player_name, player):
        response = fetch_response(
            session,
            WIKIPEDIA_SEARCH_URL,
            params={
                "search": query,
                "title": "Special:Search",
                "ns0": 1,
                "fulltext": 1,
            },
        )
        direct_page = extract_page_from_html(response)
        if direct_page is not None:
            titles.append(str(direct_page["title"]))
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select(".mw-search-result-heading a"):
            href = anchor.get("href")
            if not href or "/wiki/" not in href:
                continue
            title = unquote(href.split("/wiki/", 1)[1]).replace("_", " ").strip()
            if title:
                titles.append(title)
            if len(unique_preserve_order(titles)) >= SEARCH_RESULT_LIMIT:
                break
        if len(unique_preserve_order(titles)) >= SEARCH_RESULT_LIMIT:
            break
    return unique_preserve_order(titles)[:SEARCH_RESULT_LIMIT]


def evaluate_candidate(
    player: dict[str, object],
    candidate: dict[str, object],
    *,
    rank: int,
    exact_lookup: bool,
) -> dict[str, object]:
    player_name = str(player["player_name"])
    normalized_name = normalize_name_for_matching(player_name)
    normalized_title = normalize_text(str(candidate.get("title") or ""))
    description = str(candidate.get("description") or "")
    category_values = candidate.get("categories") or []
    category_text = " ".join(category_values)
    infobox_text = str(candidate.get("infobox_text") or "")
    combined_text = " ".join(
        [
            str(candidate.get("title") or ""),
            description,
            category_text,
            infobox_text,
            str(candidate.get("page_url") or ""),
        ]
    )
    normalized_description = normalize_text(description)
    normalized_category_text = normalize_text(category_text)
    has_thumbnail = bool(candidate.get("thumbnail_url"))
    football_related_description = is_football_related(description)
    football_related_categories = is_football_related(category_text)
    football_related = football_related_description or football_related_categories
    football_infobox = bool(candidate.get("has_football_infobox"))
    context_tokens = extract_context_tokens(player)
    candidate_tokens = extract_text_tokens(combined_text)
    context_matches = count_token_prefix_matches(context_tokens, candidate_tokens)
    player_birth_year = extract_player_birth_year(player)
    candidate_birth_year = candidate.get("birth_year")
    editions = [str(edition) for edition in player.get("editions") or []]
    normalized_combined_text = normalize_text(combined_text)
    world_cup_year_matches = [
        edition for edition in editions if normalize_text(f"{edition} fifa world cup") in normalized_combined_text
    ]
    has_world_cup_context = "fifa world cup" in normalized_combined_text or bool(world_cup_year_matches)
    wrong_sport = has_wrong_sport_signal(combined_text)
    title_aliases = {normalize_name_for_matching(alias) for alias in build_name_aliases(player_name)}
    requested_tokens = set(normalized_name.split())
    title_tokens = set(normalized_title.split())
    name_token_overlap = len(requested_tokens & title_tokens)
    min_name_similarity, average_name_similarity = best_name_token_similarity(requested_tokens, title_tokens)
    signals: list[str] = []
    rejection_reason: str | None = None

    if candidate.get("is_disambiguation"):
        signals.append("disambiguation_page")
        return {"score": 0.0, "signals": signals, "rejection_reason": "disambiguation_page"}
    if wrong_sport and not football_infobox and not football_related and not has_world_cup_context:
        signals.append("wrong_sport_signal")
        return {"score": 0.0, "signals": signals, "rejection_reason": "wrong_sport_signal"}
    if title_tokens and name_token_overlap == 0 and normalized_title not in title_aliases and average_name_similarity < 0.82:
        signals.append("name_mismatch")
        return {"score": 0.0, "signals": signals, "rejection_reason": "name_mismatch"}

    score = 0.0
    if normalized_title in title_aliases:
        score += 0.42
        signals.append("exact_alias_title_match")
    else:
        if requested_tokens and requested_tokens.issubset(title_tokens):
            score += 0.28
            signals.append("title_contains_all_name_tokens")
        elif title_tokens and title_tokens.issubset(requested_tokens):
            score += 0.18
            signals.append("title_subset_of_name_tokens")
        elif name_token_overlap >= 1:
            score += 0.14
            signals.append(f"name_token_overlap:{name_token_overlap}")
        elif average_name_similarity >= 0.88 and min_name_similarity >= 0.72:
            score += 0.16
            signals.append("fuzzy_name_match")

    if exact_lookup and normalized_title in title_aliases:
        score += 0.08
        signals.append("exact_lookup_hit")
    if rank == 0:
        score += 0.04
        signals.append("top_ranked_candidate")
    if has_thumbnail:
        score += 0.08
        signals.append("thumbnail_present")
    if football_infobox:
        score += 0.18
        signals.append("football_infobox")
    if football_related_description:
        score += 0.12
        signals.append("football_description")
    if football_related_categories:
        score += 0.08
        signals.append("football_categories")
    if context_matches >= 1:
        score += 0.12
        signals.append(f"context_match_count:{context_matches}")
    if context_matches >= 2:
        score += 0.08
    if has_world_cup_context:
        score += 0.12
        signals.append("world_cup_context")
    if world_cup_year_matches:
        score += 0.12
        signals.append(f"world_cup_year_match:{','.join(world_cup_year_matches)}")
    if "footballer" in normalized_title:
        score += 0.2
        signals.append("footballer_title_suffix")
    if wrong_sport:
        score -= 0.06
        signals.append("secondary_wrong_sport_context")
    if player_birth_year is not None and candidate_birth_year == player_birth_year:
        score += 0.05
        signals.append("birth_year_match")
    elif player_birth_year is not None and candidate_birth_year is not None and candidate_birth_year != player_birth_year:
        score -= 0.06
        signals.append("birth_year_mismatch")
    if normalized_title in title_aliases and not football_related and not football_infobox and context_matches == 0:
        score -= 0.2
        rejection_reason = "identity_context_too_weak"
    if not football_related and not has_thumbnail:
        score -= 0.2
    if has_negative_signal(f"{normalized_description} {normalized_category_text}"):
        score -= 0.35
        signals.append("negative_non_person_signal")
        rejection_reason = rejection_reason or "negative_non_person_signal"

    if not football_related and not football_infobox and context_matches == 0 and not has_world_cup_context:
        rejection_reason = rejection_reason or "insufficient_football_identity_signals"
    if not has_thumbnail:
        rejection_reason = rejection_reason or "missing_thumbnail"

    return {
        "score": max(0.0, min(score, 1.0)),
        "signals": signals,
        "rejection_reason": rejection_reason,
    }


def resolve_best_candidate(
    session: requests.Session,
    player: dict[str, object],
) -> tuple[dict[str, object] | None, dict[str, object], list[str]]:
    player_name = str(player["player_name"])
    seen_titles: set[str] = set()
    candidates: list[tuple[dict[str, object], dict[str, object]]] = []
    searched_aliases = build_searched_aliases(player)

    for title_variant in build_title_variants(player_name):
        exact_page = fetch_page_by_title(session, title_variant)
        if exact_page is None:
            continue
        title = str(exact_page["title"])
        if title in seen_titles:
            continue
        evaluation = evaluate_candidate(player, exact_page, rank=0, exact_lookup=True)
        candidates.append((exact_page, evaluation))
        seen_titles.add(title)
        if exact_page.get("thumbnail_url") and float(evaluation["score"]) >= 0.92:
            return exact_page, evaluation, searched_aliases

    for rank, title in enumerate(search_candidate_titles(session, player_name, player)):
        if title in seen_titles:
            continue
        page = fetch_page_by_title(session, title)
        if page is None:
            continue
        seen_titles.add(str(page["title"]))
        candidates.append((page, evaluate_candidate(player, page, rank=rank, exact_lookup=False)))

    if not candidates:
        return None, {"score": 0.0, "signals": [], "rejection_reason": "no_candidate_found"}, searched_aliases

    candidates.sort(key=lambda item: float(item[1]["score"]), reverse=True)
    best_candidate, best_evaluation = candidates[0]
    return best_candidate, best_evaluation, searched_aliases


def should_publish(candidate: dict[str, object], evaluation: dict[str, object]) -> bool:
    confidence = float(evaluation["score"])
    normalized_title = normalize_text(str(candidate.get("title") or ""))
    category_text = normalize_text(" ".join(candidate.get("categories") or []))
    football_related = is_football_related(
        f"{normalize_text(str(candidate.get('description') or ''))} {category_text}"
    )
    if candidate.get("is_disambiguation") or evaluation.get("rejection_reason") == "wrong_sport_signal":
        return False
    if not candidate.get("thumbnail_url"):
        return False
    if confidence >= PUBLISHED_THRESHOLD:
        return True
    return (
        confidence >= 0.78
        and (
            "footballer" in normalized_title
            or football_related
            or bool(candidate.get("has_football_infobox"))
            or any(signal.startswith("world_cup_year_match:") for signal in evaluation.get("signals", []))
        )
    )


def should_stage_for_review(evaluation: dict[str, object]) -> bool:
    if evaluation.get("rejection_reason") in {"disambiguation_page", "wrong_sport_signal"}:
        return False
    return float(evaluation["score"]) >= PENDING_REVIEW_THRESHOLD


def write_manifest_snapshot(
    manifest_entries: list[dict[str, object]],
    status_counts: dict[str, int],
) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "generated_at": utc_now(),
                "published_count": status_counts["published"],
                "pending_review_count": status_counts["pending_review"],
                "rejected_count": status_counts["rejected"],
                "unresolvable_count": status_counts["unresolvable"],
                "status_counts": status_counts,
                "entries": manifest_entries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_existing_manifest_entries() -> dict[str, dict[str, object]]:
    if not MANIFEST_PATH.exists():
        return {}
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    by_id: dict[str, dict[str, object]] = {}
    for entry in entries:
        wc_player_id = entry.get("wc_player_id")
        if wc_player_id is None:
            continue
        by_id[str(wc_player_id)] = entry
    return by_id


def build_manifest_entry(
    *,
    player: dict[str, object],
    searched_aliases: list[str],
    candidate: dict[str, object] | None,
    stage_path: Path | None,
    published_path: Path | None,
    status: str,
    confidence_score: float,
    rejection_reason: str | None,
    evidence_signals: list[str],
    notes: str | None,
) -> dict[str, object]:
    return {
        "wc_player_id": player["wc_player_id"],
        "player_name": player["player_name"],
        "searched_aliases": searched_aliases,
        "matched_page_title": candidate.get("title") if candidate else None,
        "matched_url": candidate.get("page_url") if candidate else None,
        "asset_path": to_repo_relative(stage_path) if stage_path and stage_path.exists() else None,
        "published_path": to_repo_relative(published_path) if published_path and published_path.exists() else None,
        "source": candidate.get("thumbnail_url") if candidate else None,
        "status": status,
        "confidence_score": round(confidence_score, 3),
        "evidence_signals": evidence_signals,
        "rejection_reason": rejection_reason,
        "team_slug": player["team_slug"],
        "surface_priority": player["surface_priority"],
        "confidence": round(confidence_score, 3),
        "candidate_title": candidate.get("title") if candidate else None,
        "candidate_page_url": candidate.get("page_url") if candidate else None,
        "notes": notes,
    }


def normalize_manifest_entry(
    entry: dict[str, object],
    player_lookup: dict[str, dict[str, object]],
) -> dict[str, object]:
    wc_player_id = str(entry["wc_player_id"])
    player = player_lookup.get(wc_player_id)
    searched_aliases = entry.get("searched_aliases")
    if not isinstance(searched_aliases, list) and player is not None:
        searched_aliases = build_searched_aliases(player)
    return {
        **entry,
        "searched_aliases": searched_aliases or [],
        "matched_page_title": entry.get("matched_page_title") or entry.get("candidate_title"),
        "matched_url": entry.get("matched_url") or entry.get("candidate_page_url"),
        "confidence_score": entry.get("confidence_score", entry.get("confidence")),
        "evidence_signals": entry.get("evidence_signals") or [],
        "rejection_reason": entry.get("rejection_reason"),
    }


def main() -> None:
    args = parse_args()
    reconciliation = json.loads(RECONCILIATION_PATH.read_text(encoding="utf-8"))
    players = reconciliation["players"]
    player_lookup = {str(player["wc_player_id"]): player for player in players}
    existing_entries = load_existing_manifest_entries()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json,image/*,*/*;q=0.8",
            "Referer": "https://en.wikipedia.org/",
        }
    )

    only_statuses = set(args.only_status or [])
    actionable_players = [
        player
        for player in players
        if player["decision"] in {"NO_MATCH", "NEEDS_REVIEW", "UNRESOLVABLE"}
        and existing_entries.get(str(player["wc_player_id"]), {}).get("status") != "published"
        and (
            not only_statuses
            or (
                existing_entries.get(str(player["wc_player_id"]), {}).get("status")
                or DEFAULT_STATUS_BY_DECISION.get(str(player.get("decision") or ""))
            )
            in only_statuses
        )
    ]
    actionable_ids = {str(player["wc_player_id"]) for player in actionable_players}

    manifest_entries: list[dict[str, object]] = [
        normalize_manifest_entry(entry, player_lookup)
        for wc_player_id, entry in existing_entries.items()
        if wc_player_id not in actionable_ids
    ]
    status_counts = count_manifest_statuses(manifest_entries)

    for index, player in enumerate(actionable_players, start=1):
        wc_player_id = player["wc_player_id"]
        stage_path = STAGING_DIR / f"{wc_player_id}.png"
        published_path = PUBLISHED_DIR / f"{wc_player_id}.png"
        searched_aliases = build_searched_aliases(player)
        fallback_status = build_fallback_status(player)

        try:
            candidate, evaluation, searched_aliases = resolve_best_candidate(session, player)
        except Exception as error:  # noqa: BLE001
            stage_path.unlink(missing_ok=True)
            manifest_entries.append(
                build_manifest_entry(
                    player=player,
                    searched_aliases=searched_aliases,
                    candidate=None,
                    stage_path=None,
                    published_path=None,
                    status=fallback_status,
                    confidence_score=0.0,
                    rejection_reason="request_failure",
                    evidence_signals=[],
                    notes=str(error),
                )
            )
            status_counts[fallback_status] += 1
            continue

        confidence = float(evaluation["score"])
        evidence_signals = list(evaluation.get("signals") or [])
        rejection_reason = str(evaluation.get("rejection_reason") or "") or None

        if candidate is not None:
            resolved_image_url, image_signals = resolve_candidate_image_url(session, candidate)
            if resolved_image_url:
                candidate["thumbnail_url"] = resolved_image_url
                evidence_signals.extend(image_signals)

        if candidate is None or not candidate.get("thumbnail_url"):
            stage_path.unlink(missing_ok=True)
            manifest_entries.append(
                build_manifest_entry(
                    player=player,
                    searched_aliases=searched_aliases,
                    candidate=candidate,
                    stage_path=None,
                    published_path=None,
                    status=fallback_status,
                    confidence_score=confidence,
                    rejection_reason=rejection_reason or "no_candidate_with_thumbnail",
                    evidence_signals=evidence_signals,
                    notes="No approved candidate with thumbnail found.",
                )
            )
            status_counts[fallback_status] += 1
            continue

        try:
            image_bytes = fetch_bytes(session, str(candidate["thumbnail_url"]))
            save_png(image_bytes, stage_path)
        except Exception as error:  # noqa: BLE001
            stage_path.unlink(missing_ok=True)
            manifest_entries.append(
                build_manifest_entry(
                    player=player,
                    searched_aliases=searched_aliases,
                    candidate=candidate,
                    stage_path=None,
                    published_path=None,
                    status=fallback_status,
                    confidence_score=confidence,
                    rejection_reason="image_download_failed",
                    evidence_signals=evidence_signals,
                    notes=str(error),
                )
            )
            status_counts[fallback_status] += 1
            continue

        status = fallback_status
        notes = str(candidate.get("description") or "")

        if should_publish(candidate, evaluation):
            published_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stage_path, published_path)
            status = "published"
        elif should_stage_for_review(evaluation):
            status = "pending_review"
            published_path.unlink(missing_ok=True)
        else:
            published_path.unlink(missing_ok=True)
            stage_path.unlink(missing_ok=True)
        status_counts[status] += 1

        manifest_entries.append(
            build_manifest_entry(
                player=player,
                searched_aliases=searched_aliases,
                candidate=candidate,
                stage_path=stage_path,
                published_path=published_path if status == "published" else None,
                status=status,
                confidence_score=confidence,
                rejection_reason=None if status in {"published", "pending_review"} else rejection_reason,
                evidence_signals=evidence_signals,
                notes=notes,
            )
        )

        if index % 10 == 0:
            write_manifest_snapshot(manifest_entries, status_counts)

    manifest_entries.sort(key=lambda entry: str(entry["wc_player_id"]))
    write_manifest_snapshot(manifest_entries, status_counts)

    print(
        json.dumps(
            {
                "actionable_players": len(actionable_players),
                "published_count": status_counts["published"],
                "pending_review_count": status_counts["pending_review"],
                "rejected_count": status_counts["rejected"],
                "unresolvable_count": status_counts["unresolvable"],
                "manifest_path": to_repo_relative(MANIFEST_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
