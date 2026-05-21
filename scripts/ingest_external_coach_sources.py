from __future__ import annotations

import csv
import json
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.src.core.config import get_settings
from api.src.db.client import db_client

USER_AGENT = "football-analytics-external-coach-sources/1.0 (local research)"
RUN_ID = f"external_coach_sources_{int(time.time())}"
BASE_DIR = ROOT / "data" / "external_coach_sources" / RUN_ID
RAW_DIR = BASE_DIR / "raw"
NORMALIZED_DIR = BASE_DIR / "normalized"
REPORT_DIR = BASE_DIR / "reports"
QUALITY_REPORT = ROOT / "quality" / "external_coach_sources_ingestion_report.md"
QUALITY_COVERAGE_CSV = ROOT / "quality" / "external_coach_sources_coverage.csv"
QUALITY_SUMMARY_JSON = ROOT / "quality" / "external_coach_sources_summary.json"


@dataclass(frozen=True)
class ExternalFact:
    source: str
    source_record_id: str
    source_url: str | None
    coach_external_id: str | None
    coach_name: str | None
    team_external_id: str | None
    team_name: str | None
    role: str
    start_date: str | None
    end_date: str | None
    confidence: float
    payload: dict[str, Any]


def _request_json(url: str, *, timeout: int = 90) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"), strict=False)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(2.0 * (attempt + 1))
                last_error = exc
                continue
            raise RuntimeError(f"HTTP {exc.code} url={url} body={body[:300]}") from exc
        except URLError as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise RuntimeError(f"Network error url={url}: {exc}") from exc
    raise RuntimeError(f"Retries exhausted url={url}: {last_error}")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _binding_value(binding: dict[str, Any], key: str) -> str | None:
    value = binding.get(key, {}).get("value")
    return str(value) if value is not None else None


def _entity_id(uri: str | None) -> str | None:
    if not uri:
        return None
    return uri.rstrip("/").split("/")[-1]


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).lower().strip()
    return re.sub(r"\s+", " ", text)


def _date_part(value: str | None) -> str | None:
    if not value:
        return None
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
    return match.group(1) if match else None


def _sparql(endpoint: str, query: str) -> list[dict[str, Any]]:
    url = endpoint + "?" + urlencode({"query": query, "format": "json"})
    payload = _request_json(url, timeout=120)
    return payload.get("results", {}).get("bindings", [])


def fetch_wikidata_property(prop: str, *, direction: str, limit: int = 5000) -> tuple[list[dict[str, Any]], list[ExternalFact]]:
    endpoint = "https://query.wikidata.org/sparql"
    offset = 0
    raw_rows: list[dict[str, Any]] = []
    facts: list[ExternalFact] = []

    while True:
        if direction == "person_to_team":
            pattern = f"""
              ?coach p:{prop} ?statement .
              ?statement ps:{prop} ?team .
            """
        else:
            pattern = f"""
              ?team p:{prop} ?statement .
              ?statement ps:{prop} ?coach .
            """

        query = f"""
        SELECT ?coach ?coachLabel ?team ?teamLabel ?start ?end ?statement ?rank WHERE {{
          {pattern}
          OPTIONAL {{ ?statement pq:P580 ?start . }}
          OPTIONAL {{ ?statement pq:P582 ?end . }}
          OPTIONAL {{ ?team wdt:P641 ?sport . }}
          OPTIONAL {{ ?statement wikibase:rank ?rank . }}
          FILTER(!BOUND(?sport) || ?sport = wd:Q2736)
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "pt,en,es,fr,de,it". }}
        }}
        ORDER BY ?coach ?team ?start
        LIMIT {limit}
        OFFSET {offset}
        """
        rows = _sparql(endpoint, query)
        if not rows:
            break
        for row in rows:
            raw = {key: _binding_value(row, key) for key in row}
            raw_rows.append(raw)
            statement = raw.get("statement")
            statement_id = _entity_id(statement)
            facts.append(
                ExternalFact(
                    source=f"wikidata_{prop}_{direction}",
                    source_record_id=statement_id or f"{raw.get('coach')}::{raw.get('team')}::{raw.get('start')}",
                    source_url=statement,
                    coach_external_id=_entity_id(raw.get("coach")),
                    coach_name=raw.get("coachLabel"),
                    team_external_id=_entity_id(raw.get("team")),
                    team_name=raw.get("teamLabel"),
                    role="head_coach",
                    start_date=_date_part(raw.get("start")),
                    end_date=_date_part(raw.get("end")),
                    confidence=0.72 if raw.get("start") or raw.get("end") else 0.58,
                    payload=raw,
                )
            )
        if len(rows) < limit:
            break
        offset += limit
        time.sleep(0.6)
    return raw_rows, facts


def fetch_dbpedia(limit: int = 10000, max_rows: int = 140000) -> tuple[list[dict[str, Any]], list[ExternalFact]]:
    endpoint = "https://dbpedia.org/sparql"
    offset = 0
    raw_rows: list[dict[str, Any]] = []
    facts: list[ExternalFact] = []

    while offset < max_rows:
        query = f"""
        SELECT ?coach ?coachLabel ?team ?teamLabel WHERE {{
          ?coach <http://dbpedia.org/ontology/managerClub> ?team .
          OPTIONAL {{ ?coach rdfs:label ?coachLabel . FILTER(lang(?coachLabel) = 'en') }}
          OPTIONAL {{ ?team rdfs:label ?teamLabel . FILTER(lang(?teamLabel) = 'en') }}
        }}
        LIMIT {limit}
        OFFSET {offset}
        """
        rows = _sparql(endpoint, query)
        if not rows:
            break
        for row in rows:
            raw = {key: _binding_value(row, key) for key in row}
            raw_rows.append(raw)
            coach_uri = raw.get("coach")
            team_uri = raw.get("team")
            coach_name = raw.get("coachLabel") or _entity_id(coach_uri)
            team_name = raw.get("teamLabel") or _entity_id(team_uri)
            facts.append(
                ExternalFact(
                    source="dbpedia_managerClub",
                    source_record_id=f"{coach_uri}::{team_uri}",
                    source_url=coach_uri,
                    coach_external_id=_entity_id(coach_uri),
                    coach_name=unquote(coach_name).replace("_", " ") if coach_name else None,
                    team_external_id=_entity_id(team_uri),
                    team_name=unquote(team_name).replace("_", " ") if team_name else None,
                    role="manager",
                    start_date=None,
                    end_date=None,
                    confidence=0.42,
                    payload=raw,
                )
            )
        if len(rows) < limit:
            break
        offset += limit
        time.sleep(0.8)
    return raw_rows, facts


def _mediawiki_get(lang: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urlencode(
        {"format": "json", "formatversion": "2", **params}
    )
    return _request_json(url, timeout=90)


def _search_pages(lang: str, query: str, limit: int = 10) -> list[str]:
    payload = _mediawiki_get(
        lang,
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srnamespace": 0,
        },
    )
    return [item["title"] for item in payload.get("query", {}).get("search", []) if item.get("title")]


def _fetch_page_wikitext(lang: str, title: str) -> dict[str, Any] | None:
    payload = _mediawiki_get(
        lang,
        {
            "action": "query",
            "prop": "revisions|categories",
            "titles": title,
            "rvprop": "content",
            "rvslots": "main",
            "cllimit": 500,
        },
    )
    pages = payload.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return None
    page = pages[0]
    revisions = page.get("revisions") or []
    content = None
    if revisions:
        slots = revisions[0].get("slots") or {}
        main = slots.get("main") or {}
        content = main.get("content")
    return {
        "lang": lang,
        "title": page.get("title"),
        "pageid": page.get("pageid"),
        "categories": [cat.get("title") for cat in page.get("categories") or []],
        "wikitext": content,
        "url": f"https://{lang}.wikipedia.org/wiki/{str(page.get('title')).replace(' ', '_')}",
    }


def _category_members(lang: str, category: str, limit: int = 500) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    cmcontinue: str | None = None
    while len(members) < limit:
        params: dict[str, Any] = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": min(500, limit - len(members)),
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        payload = _mediawiki_get(lang, params)
        members.extend(payload.get("query", {}).get("categorymembers", []))
        cmcontinue = payload.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break
        time.sleep(0.3)
    return members


def fetch_mediawiki_sources() -> tuple[list[dict[str, Any]], list[ExternalFact]]:
    search_terms = [
        "List of Clube de Regatas do Flamengo managers",
        "Clube de Regatas do Flamengo managers",
        "Brazil national football team managers",
        "List of Brazil national football team managers",
        "Corinthians managers",
        "Palmeiras managers",
        "Sao Paulo FC managers",
        "Santos FC managers",
        "Fluminense FC managers",
        "Botafogo FR managers",
        "CR Vasco da Gama managers",
        "Atletico Mineiro managers",
        "Real Madrid CF managers",
        "FC Barcelona managers",
        "Manchester United FC managers",
        "Liverpool FC managers",
        "Arsenal FC managers",
        "Chelsea FC managers",
        "Juventus FC managers",
        "AC Milan managers",
        "Inter Milan managers",
        "Bayern Munich managers",
        "Paris Saint-Germain FC managers",
    ]
    pt_search_terms = [
        "Lista de treinadores do Flamengo",
        "Treinadores do Clube de Regatas do Flamengo",
        "Treinadores da Seleção Brasileira de Futebol",
        "Treinadores do Corinthians",
        "Treinadores da Sociedade Esportiva Palmeiras",
        "Treinadores do São Paulo Futebol Clube",
        "Treinadores do Santos Futebol Clube",
        "Treinadores do Fluminense Football Club",
        "Treinadores do Botafogo de Futebol e Regatas",
        "Treinadores do Club de Regatas Vasco da Gama",
        "Treinadores do Clube Atlético Mineiro",
    ]
    categories = [
        ("en", "Category:Clube de Regatas do Flamengo managers"),
        ("en", "Category:Brazil national football team managers"),
        ("en", "Category:Association football managers by club"),
        ("pt", "Categoria:Treinadores do Clube de Regatas do Flamengo"),
        ("pt", "Categoria:Treinadores da Seleção Brasileira de Futebol"),
    ]

    raw_pages: list[dict[str, Any]] = []
    facts: list[ExternalFact] = []
    seen_titles: set[tuple[str, str]] = set()

    for lang, terms in [("en", search_terms), ("pt", pt_search_terms)]:
        for term in terms:
            for title in _search_pages(lang, term, limit=5):
                key = (lang, title)
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                page = _fetch_page_wikitext(lang, title)
                if not page:
                    continue
                raw_pages.append(page)
                facts.extend(_extract_mediawiki_facts(page))
                time.sleep(0.2)

    for lang, category in categories:
        members = _category_members(lang, category, limit=500)
        raw_pages.append(
            {
                "lang": lang,
                "title": category,
                "pageid": None,
                "categories": [],
                "category_members": members,
                "url": f"https://{lang}.wikipedia.org/wiki/{category.replace(' ', '_')}",
            }
        )
        for member in members:
            if member.get("ns") != 0:
                continue
            title = member.get("title")
            key = (lang, title)
            if not title or key in seen_titles:
                continue
            seen_titles.add(key)
            page = _fetch_page_wikitext(lang, title)
            if not page:
                continue
            raw_pages.append(page)
            facts.extend(_extract_mediawiki_facts(page))
            time.sleep(0.2)

    return raw_pages, facts


def _extract_mediawiki_facts(page: dict[str, Any]) -> list[ExternalFact]:
    text = page.get("wikitext") or ""
    if not text:
        return []
    facts: list[ExternalFact] = []
    title = page.get("title")
    url = page.get("url")

    manager_years = re.findall(r"\|\s*(?:manager|manageryears|manager_years)(\d*)\s*=\s*([^\n|]+)", text, flags=re.I)
    manager_clubs = re.findall(r"\|\s*(?:managerclubs|manager_clubs)(\d*)\s*=\s*([^\n|]+)", text, flags=re.I)
    clubs_by_suffix = {suffix: value for suffix, value in manager_clubs}
    for suffix, years in manager_years:
        club_value = clubs_by_suffix.get(suffix)
        if not club_value:
            continue
        cleaned_team = _clean_wikitext(club_value)
        cleaned_years = _clean_wikitext(years)
        start_year, end_year = _parse_year_range(cleaned_years)
        facts.append(
            ExternalFact(
                source=f"mediawiki_infobox_{page.get('lang')}",
                source_record_id=f"{page.get('lang')}::{title}::manager::{suffix}",
                source_url=url,
                coach_external_id=str(title),
                coach_name=str(title).replace("_", " "),
                team_external_id=cleaned_team,
                team_name=cleaned_team,
                role="manager",
                start_date=f"{start_year}-01-01" if start_year else None,
                end_date=f"{end_year}-12-31" if end_year else None,
                confidence=0.5 if start_year or end_year else 0.35,
                payload={"title": title, "years": years, "club": club_value, "url": url},
            )
        )

    if "manager" in str(title).lower() or "treinador" in str(title).lower():
        for line_number, line in enumerate(text.splitlines(), start=1):
            if re.search(r"(Flamengo|Brazil national|Sele[cç][aã]o Brasileira|manager|treinador)", line, re.I):
                cleaned = _clean_wikitext(line)
                if len(cleaned) < 8:
                    continue
                facts.append(
                    ExternalFact(
                        source=f"mediawiki_raw_line_{page.get('lang')}",
                        source_record_id=f"{page.get('lang')}::{title}::line::{line_number}",
                        source_url=url,
                        coach_external_id=None,
                        coach_name=None,
                        team_external_id=None,
                        team_name=None,
                        role="raw_text_candidate",
                        start_date=None,
                        end_date=None,
                        confidence=0.18,
                        payload={"title": title, "line_number": line_number, "line": cleaned, "url": url},
                    )
                )
    return facts


def _clean_wikitext(value: str) -> str:
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.I | re.S)
    text = re.sub(r"<ref[^/]*/>", "", text, flags=re.I)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"''+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_year_range(value: str) -> tuple[str | None, str | None]:
    years = re.findall(r"(?:19|20)\d{2}", value)
    if not years:
        return None, None
    if len(years) == 1:
        return years[0], years[0]
    return years[0], years[-1]


def _fact_to_row(fact: ExternalFact) -> dict[str, Any]:
    return {
        "source": fact.source,
        "source_record_id": fact.source_record_id,
        "source_url": fact.source_url,
        "coach_external_id": fact.coach_external_id,
        "coach_name": fact.coach_name,
        "team_external_id": fact.team_external_id,
        "team_name": fact.team_name,
        "role": fact.role,
        "start_date": fact.start_date,
        "end_date": fact.end_date,
        "confidence": fact.confidence,
        "payload": json.dumps(fact.payload, ensure_ascii=False, sort_keys=True),
    }


def _load_local_teams() -> dict[str, list[dict[str, Any]]]:
    rows = db_client.fetch_all("select team_id, team_name from mart.dim_team where team_name is not null")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_normalize_name(row["team_name"])].append(row)
    return grouped


def _local_match_teams() -> list[dict[str, Any]]:
    return db_client.fetch_all(
        """
        select match_id, competition_key, season, date_day, home_team_id as team_id
        from mart.fact_matches
        where date_day <= %s
        union all
        select match_id, competition_key, season, date_day, away_team_id as team_id
        from mart.fact_matches
        where date_day <= %s
        """,
        [get_settings().product_data_cutoff, get_settings().product_data_cutoff],
    )


def _coverage_from_external_facts(fact_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    local_teams = _load_local_teams()
    match_teams = _local_match_teams()
    intervals_by_team: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for row in fact_rows:
        team_name = row.get("team_name")
        start = row.get("start_date")
        end = row.get("end_date")
        if not team_name or not start:
            continue
        candidates = local_teams.get(_normalize_name(team_name), [])
        if not candidates:
            continue
        for candidate in candidates:
            intervals_by_team[int(candidate["team_id"])].append(row)

    grouped: dict[tuple[str, int, int], dict[str, Any]] = {}
    for match in match_teams:
        key = (match["competition_key"], int(match["season"]), int(match["team_id"]))
        bucket = grouped.setdefault(
            key,
            {
                "competition_key": match["competition_key"],
                "season": int(match["season"]),
                "team_id": int(match["team_id"]),
                "matches": 0,
                "covered_by_external_dated_fact": 0,
            },
        )
        bucket["matches"] += 1
        match_date = date.fromisoformat(str(match["date_day"]))
        for interval in intervals_by_team.get(int(match["team_id"]), []):
            start = date.fromisoformat(interval["start_date"])
            end = date.fromisoformat(interval["end_date"]) if interval.get("end_date") else get_settings().product_data_cutoff
            if start <= match_date <= end:
                bucket["covered_by_external_dated_fact"] += 1
                break

    rows = list(grouped.values())
    for row in rows:
        row["coverage_pct"] = round(100.0 * row["covered_by_external_dated_fact"] / row["matches"], 2) if row["matches"] else 0.0
    rows.sort(key=lambda item: (-item["covered_by_external_dated_fact"], item["competition_key"], item["season"], item["team_id"]))
    return rows


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    all_facts: list[ExternalFact] = []
    source_errors: list[dict[str, str]] = []
    source_counts: dict[str, int] = {}

    for prop, direction in [("P6087", "person_to_team"), ("P286", "team_to_person")]:
        try:
            raw_rows, facts = fetch_wikidata_property(prop, direction=direction)
            source_key = f"wikidata_{prop}_{direction}"
            _write_jsonl(RAW_DIR / f"{source_key}.jsonl", raw_rows)
            source_counts[source_key] = len(facts)
            all_facts.extend(facts)
        except Exception as exc:
            source_errors.append({"source": f"wikidata_{prop}_{direction}", "error": str(exc)})

    try:
        dbpedia_rows, dbpedia_facts = fetch_dbpedia()
        _write_jsonl(RAW_DIR / "dbpedia_manager_clubs.jsonl", dbpedia_rows)
        source_counts["dbpedia_managerClub"] = len(dbpedia_facts)
        all_facts.extend(dbpedia_facts)
    except Exception as exc:
        source_errors.append({"source": "dbpedia_managerClub", "error": str(exc)})

    try:
        mediawiki_rows, mediawiki_facts = fetch_mediawiki_sources()
        _write_jsonl(RAW_DIR / "mediawiki_pages_and_categories.jsonl", mediawiki_rows)
        source_counts["mediawiki"] = len(mediawiki_facts)
        all_facts.extend(mediawiki_facts)
    except Exception as exc:
        source_errors.append({"source": "mediawiki", "error": str(exc)})

    fact_rows = [_fact_to_row(fact) for fact in all_facts]
    _write_jsonl(NORMALIZED_DIR / "external_coach_facts.jsonl", fact_rows)
    _write_csv(
        NORMALIZED_DIR / "external_coach_facts.csv",
        fact_rows,
        [
            "source",
            "source_record_id",
            "source_url",
            "coach_external_id",
            "coach_name",
            "team_external_id",
            "team_name",
            "role",
            "start_date",
            "end_date",
            "confidence",
            "payload",
        ],
    )

    coverage_rows = _coverage_from_external_facts(fact_rows)
    _write_csv(
        NORMALIZED_DIR / "external_dated_fact_coverage.csv",
        coverage_rows,
        ["competition_key", "season", "team_id", "matches", "covered_by_external_dated_fact", "coverage_pct"],
    )
    _write_csv(
        QUALITY_COVERAGE_CSV,
        coverage_rows,
        ["competition_key", "season", "team_id", "matches", "covered_by_external_dated_fact", "coverage_pct"],
    )

    source_distribution = Counter(row["source"] for row in fact_rows)
    dated_count = sum(1 for row in fact_rows if row.get("start_date"))
    team_count = sum(1 for row in fact_rows if row.get("team_name"))
    coach_count = sum(1 for row in fact_rows if row.get("coach_name"))
    flamengo_facts = [
        row
        for row in fact_rows
        if "flamengo" in _normalize_name(row.get("team_name")) or "flamengo" in json.dumps(row.get("payload"), ensure_ascii=False).lower()
    ]
    top_coverage = coverage_rows[:30]
    summary = {
        "run_id": RUN_ID,
        "base_dir": str(BASE_DIR),
        "total_facts": len(fact_rows),
        "facts_with_coach_name": coach_count,
        "facts_with_team_name": team_count,
        "facts_with_start_date": dated_count,
        "source_counts": source_counts,
        "source_distribution": dict(source_distribution),
        "source_errors": source_errors,
        "flamengo_related_facts": len(flamengo_facts),
        "top_coverage_rows": top_coverage,
    }
    QUALITY_SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, flamengo_facts[:60])
    print(json.dumps(summary, ensure_ascii=False))


def _write_report(summary: dict[str, Any], flamengo_sample: list[dict[str, Any]]) -> None:
    lines = [
        "# External coach sources ingestion report",
        "",
        "## Escopo",
        "",
        "- Ambiente separado: `data/external_coach_sources/`",
        "- Nenhuma promocao para `mart.coach_identity`, `mart.coach_tenure` ou `mart.fact_coach_match_assignment`.",
        "- Fontes: Wikidata SPARQL, DBpedia SPARQL e MediaWiki API.",
        "",
        "## Totais",
        "",
        f"- Run id: `{summary['run_id']}`",
        f"- Base dir: `{summary['base_dir']}`",
        f"- Fatos externos normalizados: `{summary['total_facts']}`",
        f"- Fatos com nome de tecnico: `{summary['facts_with_coach_name']}`",
        f"- Fatos com nome de time: `{summary['facts_with_team_name']}`",
        f"- Fatos com data inicial: `{summary['facts_with_start_date']}`",
        f"- Fatos relacionados a Flamengo: `{summary['flamengo_related_facts']}`",
        "",
        "## Distribuicao por fonte",
        "",
    ]
    for source, count in sorted(summary["source_distribution"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{source}`: `{count}`")

    lines.extend(["", "## Cobertura potencial por fatos datados", ""])
    for row in summary["top_coverage_rows"][:20]:
        lines.append(
            f"- `{row['competition_key']}` {row['season']} team `{row['team_id']}`: "
            f"`{row['covered_by_external_dated_fact']}/{row['matches']}` ({row['coverage_pct']}%)"
        )

    lines.extend(["", "## Amostra Flamengo", ""])
    if flamengo_sample:
        for row in flamengo_sample:
            lines.append(
                f"- `{row['source']}` | coach `{row.get('coach_name')}` | team `{row.get('team_name')}` | "
                f"{row.get('start_date') or '?'} ate {row.get('end_date') or '?'} | conf `{row.get('confidence')}`"
            )
    else:
        lines.append("- Nenhuma linha relacionada a Flamengo foi detectada.")

    lines.extend(["", "## Erros de fonte", ""])
    if summary["source_errors"]:
        for error in summary["source_errors"]:
            lines.append(f"- `{error['source']}`: {error['error']}")
    else:
        lines.append("- Nenhum erro de fonte.")

    lines.extend(
        [
            "",
            "## Proximo acoplamento seguro",
            "",
            "- Criar camada de resolucao `external_coach_source_candidate -> coach_identity` com score de nome, data e time.",
            "- Criar camada de resolucao `external team -> dim_team` sem upsert automatico.",
            "- Promover primeiro apenas fatos com `source in wikidata_*`, time local resolvido e intervalo de datas cobrindo partida.",
            "- DBpedia e MediaWiki raw entram como evidencia auxiliar, nao como verdade final.",
        ]
    )
    QUALITY_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
