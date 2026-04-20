from __future__ import annotations

import re
import unicodedata
from typing import Any

TEAM_AND_COUNTRY_NAME_OVERRIDES = {
    "Algeria": "Argélia",
    "Australia": "Austrália",
    "Austria": "Áustria",
    "Belgium": "Bélgica",
    "Bolivia": "Bolívia",
    "Bosnia and Herzegovina": "Bósnia e Herzegovina",
    "Brazil": "Brasil",
    "Bulgaria": "Bulgária",
    "Cameroon": "Camarões",
    "Canada": "Canadá",
    "Colombia": "Colômbia",
    "Croatia": "Croácia",
    "Czech Republic": "República Tcheca",
    "Czechoslovakia": "Tchecoslováquia",
    "Denmark": "Dinamarca",
    "Dutch East Indies": "Índias Orientais Neerlandesas",
    "East Germany": "Alemanha Oriental",
    "Ecuador": "Equador",
    "Egypt": "Egito",
    "England": "Inglaterra",
    "France": "França",
    "Germany": "Alemanha",
    "Greece": "Grécia",
    "Hungary": "Hungria",
    "Iceland": "Islândia",
    "Iran": "Irã",
    "Iraq": "Iraque",
    "Italy": "Itália",
    "Ivory Coast": "Costa do Marfim",
    "Japan": "Japão",
    "Korea, Japan": "Coreia do Sul e Japão",
    "Mexico": "México",
    "Morocco": "Marrocos",
    "Netherlands": "Países Baixos",
    "New Zealand": "Nova Zelândia",
    "Nigeria": "Nigéria",
    "North Korea": "Coreia do Norte",
    "Northern Ireland": "Irlanda do Norte",
    "Norway": "Noruega",
    "Panama": "Panamá",
    "Paraguay": "Paraguai",
    "Poland": "Polônia",
    "Qatar": "Catar",
    "Republic of Ireland": "República da Irlanda",
    "Romania": "Romênia",
    "Russia": "Rússia",
    "Saudi Arabia": "Arábia Saudita",
    "Scotland": "Escócia",
    "Serbia": "Sérvia",
    "Serbia and Montenegro": "Sérvia e Montenegro",
    "Slovakia": "Eslováquia",
    "Slovenia": "Eslovênia",
    "South Africa": "África do Sul",
    "South Korea": "Coreia do Sul",
    "Soviet Union": "União Soviética",
    "Spain": "Espanha",
    "Sweden": "Suécia",
    "Switzerland": "Suíça",
    "Trinidad and Tobago": "Trinidad e Tobago",
    "Tunisia": "Tunísia",
    "Turkey": "Turquia",
    "Ukraine": "Ucrânia",
    "United Arab Emirates": "Emirados Árabes Unidos",
    "United States": "Estados Unidos",
    "Uruguay": "Uruguai",
    "Wales": "País de Gales",
    "West Germany": "Alemanha Ocidental",
    "Yugoslavia": "Iugoslávia",
}

WORLD_CUP_CANONICAL_DISPLAY_TEAMS = {
    "germany": {
        "display_team_id": "world-cup-germany",
        "display_team_name": "Alemanha",
    },
    "west germany": {
        "display_team_id": "world-cup-germany",
        "display_team_name": "Alemanha",
    },
    "alemanha": {
        "display_team_id": "world-cup-germany",
        "display_team_name": "Alemanha",
    },
    "alemanha ocidental": {
        "display_team_id": "world-cup-germany",
        "display_team_name": "Alemanha",
    },
}

VENUE_NAME_OVERRIDES = {
    "Estadio Azteca": "Estádio Azteca",
    "Estadio Centenario": "Estádio Centenário",
    "Estadio Monumental": "Estádio Monumental",
    "Estadio Nacional": "Estádio Nacional",
    "Estadio Santiago Bernabéu": "Estádio Santiago Bernabéu",
    "Estádio do Maracană": "Estádio do Maracanã",
    "International Stadium Yokohama": "Estádio Internacional de Yokohama",
    "Lusail Stadium": "Estádio Lusail",
    "Olympiastadion": "Estádio Olímpico de Berlim",
    "Rĺsunda Stadium": "Estádio Råsunda",
    "Stade Olympique de Colombes": "Estádio Olímpico de Colombes",
    "Stadio Nazionale PNF": "Stádio Nazionale PNF",
    "Stadio Olimpico": "Stádio Olímpico de Roma",
    "Stadion Luzhniki": "Estádio Lujniki",
    "Wankdorf Stadium": "Estádio Wankdorf",
    "Wembley Stadium": "Estádio de Wembley",
    "Råsunda Stadium": "Estádio Råsunda",
}


def _normalize_compare_key(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()
    if not normalized_value:
        return None

    return normalized_value.casefold()


def translate_world_cup_display_name(value: str | None) -> str | None:
    if value is None:
        return None

    return TEAM_AND_COUNTRY_NAME_OVERRIDES.get(value, value)


def translate_world_cup_venue_name(value: str | None) -> str | None:
    if value is None:
        return None

    return VENUE_NAME_OVERRIDES.get(value, value)


def serialize_world_cup_display_team(team_id: int | str | None, team_name: str | None) -> dict[str, Any] | None:
    translated_team_name = translate_world_cup_display_name(team_name)
    normalized_team_name = _normalize_compare_key(translated_team_name)
    canonical_team = WORLD_CUP_CANONICAL_DISPLAY_TEAMS.get(normalized_team_name or "")

    normalized_team_id = None
    if team_id is not None:
        team_id_value = str(team_id).strip()
        normalized_team_id = team_id_value or None

    display_team_id = canonical_team["display_team_id"] if canonical_team else normalized_team_id
    display_team_name = canonical_team["display_team_name"] if canonical_team else translated_team_name

    if display_team_id is None and display_team_name is None:
        return None

    return {
        "teamId": display_team_id,
        "teamName": display_team_name,
    }


def build_world_cup_country_key(value: str | None) -> str | None:
    translated_value = translate_world_cup_display_name(value)
    normalized_value = _normalize_compare_key(translated_value)
    if normalized_value is None:
        return None

    ascii_normalized = (
        unicodedata.normalize("NFKD", normalized_value).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_normalized).strip("_") or None


def build_world_cup_edition_name(season_label: str) -> str:
    return f"Copa do Mundo FIFA {season_label}"
