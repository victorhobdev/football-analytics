from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psycopg

from _repo_root import resolve_repo_root


ROOT = resolve_repo_root()
DEFAULT_ENV_PATH = ROOT / ".env"
DEFAULT_DATASET_ROOT = ROOT / "warehouse" / "_inspect"
DEFAULT_SUMMARY_JSON = ROOT / "platform" / "reports" / "quality" / "external_warehouse_ingestion_summary.json"
DEFAULT_SUMMARY_MD = ROOT / "platform" / "reports" / "quality" / "external_warehouse_ingestion_summary.md"


@dataclass(frozen=True)
class CsvLoadSpec:
    phase: str
    source_name: str
    source_kind: str
    usage_scope: str
    license_summary: str
    terms_summary: str
    relative_path: str
    target_table: str
    column_map: tuple[tuple[str, str], ...]
    encoding: str
    row_filter: Callable[[dict[str, str]], bool] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingestao dos datasets externos de warehouse (Brasileirao, Elo/Matches e "
            "Transfermarkt) com isolamento por fonte e idempotencia por record_hash."
        )
    )
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--dataset-root", default=str(DEFAULT_DATASET_ROOT))
    parser.add_argument("--summary-json", default=str(DEFAULT_SUMMARY_JSON))
    parser.add_argument("--summary-md", default=str(DEFAULT_SUMMARY_MD))
    parser.add_argument(
        "--phase",
        choices=("all", "brasileirao", "elo", "tm-core", "tm-heavy"),
        default="all",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_run_id() -> str:
    return utc_now().strftime("%Y-%m-%dT%H%M%SZ")


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def resolve_setting(name: str, env_values: dict[str, str], default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    return env_values.get(name, default)


def resolve_pg_dsn(env_values: dict[str, str]) -> str:
    dsn = (
        resolve_setting("FOOTBALL_PG_DSN", env_values)
        or resolve_setting("DATABASE_URL", env_values)
        or "postgresql://football:football@localhost:5432/football_dw"
    )
    if dsn.startswith("postgresql+psycopg2://"):
        dsn = "postgresql://" + dsn.removeprefix("postgresql+psycopg2://")
    if dsn.startswith("postgresql+psycopg://"):
        dsn = "postgresql://" + dsn.removeprefix("postgresql+psycopg://")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn.removeprefix("postgres://")
    if "@postgres:" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres:", "@localhost:")
    if "@postgres/" in dsn and not os.getenv("RUNNING_IN_DOCKER"):
        dsn = dsn.replace("@postgres/", "@localhost/")
    return dsn


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def clean_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\x00", "").strip()
    if text == "":
        return None
    return text


def row_hash(source_name: str, source_file: str, values: list[str | None]) -> str:
    joined = "|".join("" if value is None else value for value in values)
    return hashlib.sha256(f"{source_name}|{source_file}|{joined}".encode("utf-8", "ignore")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_keep_transfer_row(row: dict[str, str]) -> bool:
    raw_date = clean_value(row.get("transfer_date"))
    if raw_date is None:
        return True
    try:
        return date.fromisoformat(raw_date[:10]) <= date.today()
    except ValueError:
        return True


SPECS: tuple[CsvLoadSpec, ...] = (
    CsvLoadSpec(
        phase="brasileirao",
        source_name="dataset_brasileirao",
        source_kind="csv_bundle",
        usage_scope="academic_local",
        license_summary="Kaggle dataset de Brasileirao Serie A; revisar redistribuicao antes de publicar.",
        terms_summary="Uso local academico; fonte externa com sobreposicao parcial ao core.",
        relative_path=r"brasileirao\campeonato-brasileiro-full.csv",
        target_table="raw.brasileirao_matches",
        column_map=(
            ("ID", "match_id"),
            ("rodata", "rodada"),
            ("data", "match_date_raw"),
            ("hora", "match_time_raw"),
            ("mandante", "home_team_name"),
            ("visitante", "away_team_name"),
            ("formacao_mandante", "home_formation"),
            ("formacao_visitante", "away_formation"),
            ("tecnico_mandante", "home_coach_name"),
            ("tecnico_visitante", "away_coach_name"),
            ("vencedor", "winner_name"),
            ("arena", "venue_name"),
            ("mandante_Placar", "home_score"),
            ("visitante_Placar", "away_score"),
            ("mandante_Estado", "home_state"),
            ("visitante_Estado", "away_state"),
            ("arrecadacao", "revenue_raw"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="brasileirao",
        source_name="dataset_brasileirao",
        source_kind="csv_bundle",
        usage_scope="academic_local",
        license_summary="Kaggle dataset de Brasileirao Serie A; revisar redistribuicao antes de publicar.",
        terms_summary="Uso local academico; fonte externa com sobreposicao parcial ao core.",
        relative_path=r"brasileirao\campeonato-brasileiro-estatisticas-full.csv",
        target_table="raw.brasileirao_stats",
        column_map=(
            ("partida_id", "partida_id"),
            ("rodata", "rodada"),
            ("clube", "clube"),
            ("chutes", "chutes"),
            ("chutes_no_alvo", "chutes_no_alvo"),
            ("posse_de_bola", "posse_de_bola"),
            ("passes", "passes"),
            ("precisao_passes", "precisao_passes"),
            ("faltas", "faltas"),
            ("cartao_amarelo", "cartao_amarelo"),
            ("cartao_vermelho", "cartao_vermelho"),
            ("impedimentos", "impedimentos"),
            ("escanteios", "escanteios"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="brasileirao",
        source_name="dataset_brasileirao",
        source_kind="csv_bundle",
        usage_scope="academic_local",
        license_summary="Kaggle dataset de Brasileirao Serie A; revisar redistribuicao antes de publicar.",
        terms_summary="Uso local academico; fonte externa com sobreposicao parcial ao core.",
        relative_path=r"brasileirao\campeonato-brasileiro-gols.csv",
        target_table="raw.brasileirao_goals",
        column_map=(
            ("partida_id", "partida_id"),
            ("rodata", "rodada"),
            ("clube", "clube"),
            ("atleta", "atleta"),
            ("minuto", "minuto"),
            ("tipo_de_gol", "tipo_de_gol"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="brasileirao",
        source_name="dataset_brasileirao",
        source_kind="csv_bundle",
        usage_scope="academic_local",
        license_summary="Kaggle dataset de Brasileirao Serie A; revisar redistribuicao antes de publicar.",
        terms_summary="Uso local academico; fonte externa com sobreposicao parcial ao core.",
        relative_path=r"brasileirao\campeonato-brasileiro-cartoes.csv",
        target_table="raw.brasileirao_cards",
        column_map=(
            ("partida_id", "partida_id"),
            ("rodata", "rodada"),
            ("clube", "clube"),
            ("cartao", "cartao"),
            ("atleta", "atleta"),
            ("num_camisa", "num_camisa"),
            ("posicao", "posicao"),
            ("minuto", "minuto"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="elo",
        source_name="dataset_elo_matches",
        source_kind="csv_bundle",
        usage_scope="academic_local",
        license_summary="Club Elo + Football-Data style dataset; revisar redistribuicao antes de publicar.",
        terms_summary="Uso local academico com grande valor analitico para odds e ratings.",
        relative_path=r"dataset-00a25\EloRatings.csv",
        target_table="raw.elo_ratings",
        column_map=(
            ("date", "rating_date_raw"),
            ("club", "club_name"),
            ("country", "country_code"),
            ("elo", "elo_rating_raw"),
        ),
        encoding="utf-8-sig",
    ),
    CsvLoadSpec(
        phase="elo",
        source_name="dataset_elo_matches",
        source_kind="csv_bundle",
        usage_scope="academic_local",
        license_summary="Club Elo + Football-Data style dataset; revisar redistribuicao antes de publicar.",
        terms_summary="Uso local academico com grande valor analitico para odds e ratings.",
        relative_path=r"dataset-00a25\Matches.csv",
        target_table="raw.elo_matches",
        column_map=(
            ("Division", "division"),
            ("MatchDate", "match_date_raw"),
            ("MatchTime", "match_time_raw"),
            ("HomeTeam", "home_team_name"),
            ("AwayTeam", "away_team_name"),
            ("HomeElo", "home_elo_raw"),
            ("AwayElo", "away_elo_raw"),
            ("Form3Home", "form3_home_raw"),
            ("Form5Home", "form5_home_raw"),
            ("Form3Away", "form3_away_raw"),
            ("Form5Away", "form5_away_raw"),
            ("FTHome", "ft_home_raw"),
            ("FTAway", "ft_away_raw"),
            ("FTResult", "ft_result"),
            ("HTHome", "ht_home_raw"),
            ("HTAway", "ht_away_raw"),
            ("HTResult", "ht_result"),
            ("HomeShots", "home_shots_raw"),
            ("AwayShots", "away_shots_raw"),
            ("HomeTarget", "home_target_raw"),
            ("AwayTarget", "away_target_raw"),
            ("HomeFouls", "home_fouls_raw"),
            ("AwayFouls", "away_fouls_raw"),
            ("HomeCorners", "home_corners_raw"),
            ("AwayCorners", "away_corners_raw"),
            ("HomeYellow", "home_yellow_raw"),
            ("AwayYellow", "away_yellow_raw"),
            ("HomeRed", "home_red_raw"),
            ("AwayRed", "away_red_raw"),
            ("OddHome", "odd_home_raw"),
            ("OddDraw", "odd_draw_raw"),
            ("OddAway", "odd_away_raw"),
            ("MaxHome", "max_home_raw"),
            ("MaxDraw", "max_draw_raw"),
            ("MaxAway", "max_away_raw"),
            ("Over25", "over25_raw"),
            ("Under25", "under25_raw"),
            ("MaxOver25", "max_over25_raw"),
            ("MaxUnder25", "max_under25_raw"),
            ("HandiSize", "handi_size_raw"),
            ("HandiHome", "handi_home_raw"),
            ("HandiAway", "handi_away_raw"),
            ("C_LTH", "c_lth_raw"),
            ("C_LTA", "c_lta_raw"),
            ("C_VHD", "c_vhd_raw"),
            ("C_VAD", "c_vad_raw"),
            ("C_HTB", "c_htb_raw"),
            ("C_PHB", "c_phb_raw"),
        ),
        encoding="utf-8-sig",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\competitions.csv",
        target_table="raw.tm_competitions",
        column_map=(
            ("competition_id", "competition_id"),
            ("competition_code", "competition_code"),
            ("name", "name"),
            ("sub_type", "sub_type"),
            ("type", "type"),
            ("country_id", "country_id"),
            ("country_name", "country_name"),
            ("domestic_league_code", "domestic_league_code"),
            ("confederation", "confederation"),
            ("total_clubs", "total_clubs"),
            ("url", "url"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\countries.csv",
        target_table="raw.tm_countries",
        column_map=(
            ("country_id", "country_id"),
            ("country_name", "country_name"),
            ("country_code", "country_code"),
            ("confederation", "confederation"),
            ("total_clubs", "total_clubs"),
            ("total_players", "total_players"),
            ("average_age", "average_age"),
            ("url", "url"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\national_teams.csv",
        target_table="raw.tm_national_teams",
        column_map=(
            ("national_team_id", "national_team_id"),
            ("name", "name"),
            ("team_code", "team_code"),
            ("country_id", "country_id"),
            ("country_name", "country_name"),
            ("country_code", "country_code"),
            ("confederation", "confederation"),
            ("team_image_url", "team_image_url"),
            ("squad_size", "squad_size"),
            ("average_age", "average_age"),
            ("foreigners_number", "foreigners_number"),
            ("foreigners_percentage", "foreigners_percentage"),
            ("total_market_value", "total_market_value"),
            ("coach_name", "coach_name"),
            ("fifa_ranking", "fifa_ranking"),
            ("last_season", "last_season"),
            ("url", "url"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\clubs.csv",
        target_table="raw.tm_clubs",
        column_map=(
            ("club_id", "club_id"),
            ("club_code", "club_code"),
            ("name", "name"),
            ("domestic_competition_id", "domestic_competition_id"),
            ("total_market_value", "total_market_value"),
            ("squad_size", "squad_size"),
            ("average_age", "average_age"),
            ("foreigners_number", "foreigners_number"),
            ("foreigners_percentage", "foreigners_percentage"),
            ("national_team_players", "national_team_players"),
            ("stadium_name", "stadium_name"),
            ("stadium_seats", "stadium_seats"),
            ("net_transfer_record", "net_transfer_record"),
            ("coach_name", "coach_name"),
            ("last_season", "last_season"),
            ("filename", "filename"),
            ("url", "url"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\players.csv",
        target_table="raw.tm_players",
        column_map=(
            ("player_id", "player_id"),
            ("first_name", "first_name"),
            ("last_name", "last_name"),
            ("name", "name"),
            ("last_season", "last_season"),
            ("current_club_id", "current_club_id"),
            ("player_code", "player_code"),
            ("country_of_birth", "country_of_birth"),
            ("city_of_birth", "city_of_birth"),
            ("country_of_citizenship", "country_of_citizenship"),
            ("date_of_birth", "date_of_birth_raw"),
            ("sub_position", "sub_position"),
            ("position", "position"),
            ("foot", "foot"),
            ("height_in_cm", "height_in_cm"),
            ("contract_expiration_date", "contract_expiration_date_raw"),
            ("agent_name", "agent_name"),
            ("image_url", "image_url"),
            ("international_caps", "international_caps"),
            ("international_goals", "international_goals"),
            ("current_national_team_id", "current_national_team_id"),
            ("url", "url"),
            ("current_club_domestic_competition_id", "current_club_domestic_competition_id"),
            ("current_club_name", "current_club_name"),
            ("market_value_in_eur", "market_value_in_eur"),
            ("highest_market_value_in_eur", "highest_market_value_in_eur"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\games.csv",
        target_table="raw.tm_games",
        column_map=(
            ("game_id", "game_id"),
            ("competition_id", "competition_id"),
            ("season", "season"),
            ("round", "round"),
            ("date", "match_date_raw"),
            ("home_club_id", "home_club_id"),
            ("away_club_id", "away_club_id"),
            ("home_club_goals", "home_club_goals"),
            ("away_club_goals", "away_club_goals"),
            ("home_club_position", "home_club_position"),
            ("away_club_position", "away_club_position"),
            ("home_club_manager_name", "home_club_manager_name"),
            ("away_club_manager_name", "away_club_manager_name"),
            ("stadium", "stadium"),
            ("attendance", "attendance"),
            ("referee", "referee"),
            ("url", "url"),
            ("home_club_formation", "home_club_formation"),
            ("away_club_formation", "away_club_formation"),
            ("home_club_name", "home_club_name"),
            ("away_club_name", "away_club_name"),
            ("aggregate", "aggregate"),
            ("competition_type", "competition_type"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\club_games.csv",
        target_table="raw.tm_club_games",
        column_map=(
            ("game_id", "game_id"),
            ("club_id", "club_id"),
            ("own_goals", "own_goals"),
            ("own_position", "own_position"),
            ("own_manager_name", "own_manager_name"),
            ("opponent_id", "opponent_id"),
            ("opponent_goals", "opponent_goals"),
            ("opponent_position", "opponent_position"),
            ("opponent_manager_name", "opponent_manager_name"),
            ("hosting", "hosting"),
            ("is_win", "is_win"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\player_valuations.csv",
        target_table="raw.tm_player_valuations",
        column_map=(
            ("player_id", "player_id"),
            ("date", "valuation_date_raw"),
            ("market_value_in_eur", "market_value_in_eur"),
            ("current_club_name", "current_club_name"),
            ("current_club_id", "current_club_id"),
            ("player_club_domestic_competition_id", "player_club_domestic_competition_id"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-core",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\transfers.csv",
        target_table="raw.tm_transfers",
        column_map=(
            ("player_id", "player_id"),
            ("transfer_date", "transfer_date_raw"),
            ("transfer_season", "transfer_season"),
            ("from_club_id", "from_club_id"),
            ("to_club_id", "to_club_id"),
            ("from_club_name", "from_club_name"),
            ("to_club_name", "to_club_name"),
            ("transfer_fee", "transfer_fee"),
            ("market_value_in_eur", "market_value_in_eur"),
            ("player_name", "player_name"),
        ),
        encoding="cp1252",
        row_filter=should_keep_transfer_row,
    ),
    CsvLoadSpec(
        phase="tm-heavy",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\appearances.csv",
        target_table="raw.tm_appearances",
        column_map=(
            ("appearance_id", "appearance_id"),
            ("game_id", "game_id"),
            ("player_id", "player_id"),
            ("player_club_id", "player_club_id"),
            ("player_current_club_id", "player_current_club_id"),
            ("date", "match_date_raw"),
            ("player_name", "player_name"),
            ("competition_id", "competition_id"),
            ("yellow_cards", "yellow_cards"),
            ("red_cards", "red_cards"),
            ("goals", "goals"),
            ("assists", "assists"),
            ("minutes_played", "minutes_played"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-heavy",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\game_events.csv",
        target_table="raw.tm_game_events",
        column_map=(
            ("game_event_id", "game_event_id"),
            ("date", "match_date_raw"),
            ("game_id", "game_id"),
            ("minute", "minute"),
            ("type", "type"),
            ("club_id", "club_id"),
            ("club_name", "club_name"),
            ("player_id", "player_id"),
            ("description", "description"),
            ("player_in_id", "player_in_id"),
            ("player_assist_id", "player_assist_id"),
        ),
        encoding="cp1252",
    ),
    CsvLoadSpec(
        phase="tm-heavy",
        source_name="dataset_transfermarket",
        source_kind="csv_bundle",
        usage_scope="experimental_not_for_redistribution",
        license_summary="Transfermarkt-derived dataset via Kaggle/scraper publico; nao redistribuir sem revisao juridica.",
        terms_summary="Uso local experimental; forte risco de termos de origem.",
        relative_path=r"transfermarket\game_lineups.csv",
        target_table="raw.tm_game_lineups",
        column_map=(
            ("game_lineups_id", "game_lineups_id"),
            ("date", "match_date_raw"),
            ("game_id", "game_id"),
            ("player_id", "player_id"),
            ("club_id", "club_id"),
            ("player_name", "player_name"),
            ("type", "lineup_type"),
            ("position", "position"),
            ("number", "shirt_number"),
            ("team_captain", "team_captain"),
        ),
        encoding="cp1252",
    ),
)


def specs_for_phase(phase: str) -> list[CsvLoadSpec]:
    if phase == "all":
        return list(SPECS)
    return [spec for spec in SPECS if spec.phase == phase]


def upsert_source(conn: psycopg.Connection[Any], spec: CsvLoadSpec, source_root: Path) -> None:
    conn.execute(
        """
        insert into control.external_data_sources (
          source_name, source_kind, source_root, license_summary, attribution_required, usage_scope, terms_summary
        )
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (source_name) do update
          set source_kind = excluded.source_kind,
              source_root = excluded.source_root,
              license_summary = excluded.license_summary,
              attribution_required = excluded.attribution_required,
              usage_scope = excluded.usage_scope,
              terms_summary = excluded.terms_summary,
              updated_at = now()
        """,
        (
            spec.source_name,
            spec.source_kind,
            str(source_root),
            spec.license_summary,
            False,
            spec.usage_scope,
            spec.terms_summary,
        ),
    )


def upsert_manifest(conn: psycopg.Connection[Any], spec: CsvLoadSpec, dataset_root: Path, csv_path: Path) -> None:
    relative_path = str(csv_path.relative_to(dataset_root)).replace("\\", "/")
    conn.execute(
        """
        insert into control.external_file_manifest (
          source_name, relative_path, detected_entity, provider_match_id, file_size_bytes, sha256, load_status, parse_error
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (source_name, relative_path) do update
          set detected_entity = excluded.detected_entity,
              file_size_bytes = excluded.file_size_bytes,
              sha256 = excluded.sha256,
              load_status = excluded.load_status,
              parse_error = excluded.parse_error,
              updated_at = now()
        """,
        (
            spec.source_name,
            relative_path,
            spec.target_table,
            None,
            csv_path.stat().st_size,
            file_sha256(csv_path),
            "loaded",
            None,
        ),
    )


def ingest_csv(conn: psycopg.Connection[Any], dataset_root: Path, spec: CsvLoadSpec) -> dict[str, Any]:
    csv_path = dataset_root / spec.relative_path
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV nao encontrado: {csv_path}")

    target_columns = ["record_hash", "source_name", *[dest for _, dest in spec.column_map], "source_file", "ingested_at"]
    temp_table = f"temp_{spec.target_table.split('.')[-1]}_{utc_run_id().replace('-', '').replace(':', '').replace('T', '_').replace('Z', '')}"

    inserted_rows = 0
    kept_rows = 0
    skipped_rows = 0
    ingested_at = utc_now()

    conn.execute(f"create temp table {temp_table} (like {spec.target_table} including defaults) on commit drop")
    with csv_path.open("r", encoding=spec.encoding, errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        with conn.cursor() as cursor:
            with cursor.copy(
                f"COPY {temp_table} ({', '.join(target_columns)}) FROM STDIN"
            ) as copy:
                for row in reader:
                    if spec.row_filter is not None and not spec.row_filter(row):
                        skipped_rows += 1
                        continue
                    values = [clean_value(row.get(source)) for source, _ in spec.column_map]
                    payload = [
                        row_hash(spec.source_name, spec.relative_path, values),
                        spec.source_name,
                        *values,
                        spec.relative_path.replace("\\", "/"),
                        ingested_at,
                    ]
                    copy.write_row(payload)
                    kept_rows += 1

    conflict_column = "record_hash"
    inserted_rows = conn.execute(
        f"""
        insert into {spec.target_table} ({', '.join(target_columns)})
        select {', '.join(target_columns)} from {temp_table}
        on conflict ({conflict_column}) do nothing
        """
    ).rowcount

    upsert_source(conn, spec, dataset_root)
    upsert_manifest(conn, spec, dataset_root, csv_path)

    return {
        "target_table": spec.target_table,
        "source_name": spec.source_name,
        "relative_path": spec.relative_path.replace("\\", "/"),
        "rows_seen_after_filter": kept_rows,
        "rows_skipped": skipped_rows,
        "rows_inserted": inserted_rows,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# External warehouse ingestion summary",
        "",
        f"- Run id: `{summary['run_id']}`",
        f"- Dataset root: `{summary['dataset_root']}`",
        f"- Phase: `{summary['phase']}`",
        "",
        "## Tables",
        "",
        "| Table | Source | Inserted | Seen | Skipped | File |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for item in summary["tables"]:
        lines.append(
            f"| `{item['target_table']}` | `{item['source_name']}` | `{item['rows_inserted']}` | "
            f"`{item['rows_seen_after_filter']}` | `{item['rows_skipped']}` | `{item['relative_path']}` |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    env_values = load_env_file(Path(args.env_file))
    dsn = resolve_pg_dsn(env_values)
    dataset_root = Path(args.dataset_root)
    specs = specs_for_phase(args.phase)

    summary = {
        "run_id": utc_run_id(),
        "dataset_root": str(dataset_root),
        "phase": args.phase,
        "tables": [],
    }

    if args.dry_run:
        for spec in specs:
            csv_path = dataset_root / spec.relative_path
            summary["tables"].append(
                {
                    "target_table": spec.target_table,
                    "source_name": spec.source_name,
                    "relative_path": spec.relative_path.replace("\\", "/"),
                    "rows_seen_after_filter": 0,
                    "rows_skipped": 0,
                    "rows_inserted": 0,
                    "exists": csv_path.exists(),
                }
            )
    else:
        with psycopg.connect(dsn, autocommit=False) as conn:
            for spec in specs:
                result = ingest_csv(conn, dataset_root, spec)
                summary["tables"].append(result)
            conn.commit()

    ensure_parent(Path(args.summary_json))
    ensure_parent(Path(args.summary_md))
    Path(args.summary_json).write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    Path(args.summary_md).write_text(render_markdown(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
