from __future__ import annotations

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

WORLD_CUP_CANONICAL_TEAM_VARIANTS = (
    ("world-cup-algeria", "Argélia", ("Algeria", "Argélia")),
    ("world-cup-angola", "Angola", ("Angola",)),
    ("world-cup-argentina", "Argentina", ("Argentina",)),
    ("world-cup-australia", "Austrália", ("Australia", "Austrália")),
    ("world-cup-austria", "Áustria", ("Austria", "Áustria")),
    ("world-cup-belgium", "Bélgica", ("Belgium", "Bélgica")),
    ("world-cup-bolivia", "Bolívia", ("Bolivia", "Bolívia")),
    ("world-cup-bosnia-and-herzegovina", "Bósnia e Herzegovina", ("Bosnia and Herzegovina", "Bósnia e Herzegovina")),
    ("world-cup-brazil", "Brasil", ("Brazil", "Brasil")),
    ("world-cup-bulgaria", "Bulgária", ("Bulgaria", "Bulgária")),
    ("world-cup-cameroon", "Camarões", ("Cameroon", "Camarões")),
    ("world-cup-canada", "Canadá", ("Canada", "Canadá")),
    ("world-cup-chile", "Chile", ("Chile",)),
    ("world-cup-china", "China", ("China",)),
    ("world-cup-colombia", "Colômbia", ("Colombia", "Colômbia")),
    ("world-cup-costa-rica", "Costa Rica", ("Costa Rica",)),
    ("world-cup-croatia", "Croácia", ("Croatia", "Croácia")),
    ("world-cup-cuba", "Cuba", ("Cuba",)),
    ("world-cup-czech-republic", "República Tcheca", ("Czech Republic", "República Tcheca")),
    ("world-cup-czechoslovakia", "Tchecoslováquia", ("Czechoslovakia", "Tchecoslováquia")),
    ("world-cup-denmark", "Dinamarca", ("Denmark", "Dinamarca")),
    ("world-cup-dutch-east-indies", "Índias Orientais Neerlandesas", ("Dutch East Indies", "Índias Orientais Neerlandesas")),
    ("world-cup-east-germany", "Alemanha Oriental", ("East Germany", "Alemanha Oriental")),
    ("world-cup-ecuador", "Equador", ("Ecuador", "Equador")),
    ("world-cup-egypt", "Egito", ("Egypt", "Egito")),
    ("world-cup-el-salvador", "El Salvador", ("El Salvador",)),
    ("world-cup-england", "Inglaterra", ("England", "Inglaterra")),
    ("world-cup-france", "França", ("France", "França")),
    ("world-cup-germany", "Alemanha", ("Germany", "Alemanha", "West Germany", "Alemanha Ocidental")),
    ("world-cup-ghana", "Ghana", ("Ghana",)),
    ("world-cup-greece", "Grécia", ("Greece", "Grécia")),
    ("world-cup-haiti", "Haiti", ("Haiti",)),
    ("world-cup-honduras", "Honduras", ("Honduras",)),
    ("world-cup-hungary", "Hungria", ("Hungary", "Hungria")),
    ("world-cup-iceland", "Islândia", ("Iceland", "Islândia")),
    ("world-cup-iran", "Irã", ("Iran", "Irã")),
    ("world-cup-iraq", "Iraque", ("Iraq", "Iraque")),
    ("world-cup-israel", "Israel", ("Israel",)),
    ("world-cup-italy", "Itália", ("Italy", "Itália")),
    ("world-cup-ivory-coast", "Costa do Marfim", ("Ivory Coast", "Costa do Marfim")),
    ("world-cup-jamaica", "Jamaica", ("Jamaica",)),
    ("world-cup-japan", "Japão", ("Japan", "Japão")),
    ("world-cup-kuwait", "Kuwait", ("Kuwait",)),
    ("world-cup-mexico", "México", ("Mexico", "México")),
    ("world-cup-morocco", "Marrocos", ("Morocco", "Marrocos")),
    ("world-cup-netherlands", "Países Baixos", ("Netherlands", "Países Baixos")),
    ("world-cup-new-zealand", "Nova Zelândia", ("New Zealand", "Nova Zelândia")),
    ("world-cup-nigeria", "Nigéria", ("Nigeria", "Nigéria")),
    ("world-cup-north-korea", "Coreia do Norte", ("North Korea", "Coreia do Norte")),
    ("world-cup-northern-ireland", "Irlanda do Norte", ("Northern Ireland", "Irlanda do Norte")),
    ("world-cup-norway", "Noruega", ("Norway", "Noruega")),
    ("world-cup-panama", "Panamá", ("Panama", "Panamá")),
    ("world-cup-paraguay", "Paraguai", ("Paraguay", "Paraguai")),
    ("world-cup-peru", "Peru", ("Peru",)),
    ("world-cup-poland", "Polônia", ("Poland", "Polônia")),
    ("world-cup-portugal", "Portugal", ("Portugal",)),
    ("world-cup-qatar", "Catar", ("Qatar", "Catar")),
    ("world-cup-republic-of-ireland", "República da Irlanda", ("Republic of Ireland", "República da Irlanda")),
    ("world-cup-romania", "Romênia", ("Romania", "Romênia")),
    ("world-cup-russia", "Rússia", ("Russia", "Rússia")),
    ("world-cup-saudi-arabia", "Arábia Saudita", ("Saudi Arabia", "Arábia Saudita")),
    ("world-cup-scotland", "Escócia", ("Scotland", "Escócia")),
    ("world-cup-senegal", "Senegal", ("Senegal",)),
    ("world-cup-serbia", "Sérvia", ("Serbia", "Sérvia")),
    ("world-cup-serbia-and-montenegro", "Sérvia e Montenegro", ("Serbia and Montenegro", "Sérvia e Montenegro")),
    ("world-cup-slovakia", "Eslováquia", ("Slovakia", "Eslováquia")),
    ("world-cup-slovenia", "Eslovênia", ("Slovenia", "Eslovênia")),
    ("world-cup-south-africa", "África do Sul", ("South Africa", "África do Sul")),
    ("world-cup-south-korea", "Coreia do Sul", ("South Korea", "Coreia do Sul")),
    ("world-cup-soviet-union", "União Soviética", ("Soviet Union", "União Soviética")),
    ("world-cup-spain", "Espanha", ("Spain", "Espanha")),
    ("world-cup-sweden", "Suécia", ("Sweden", "Suécia")),
    ("world-cup-switzerland", "Suíça", ("Switzerland", "Suíça")),
    ("world-cup-togo", "Togo", ("Togo",)),
    ("world-cup-trinidad-and-tobago", "Trinidad e Tobago", ("Trinidad and Tobago", "Trinidad e Tobago")),
    ("world-cup-tunisia", "Tunísia", ("Tunisia", "Tunísia")),
    ("world-cup-turkey", "Turquia", ("Turkey", "Turquia")),
    ("world-cup-ukraine", "Ucrânia", ("Ukraine", "Ucrânia")),
    ("world-cup-united-arab-emirates", "Emirados Árabes Unidos", ("United Arab Emirates", "Emirados Árabes Unidos")),
    ("world-cup-united-states", "Estados Unidos", ("United States", "Estados Unidos")),
    ("world-cup-uruguay", "Uruguai", ("Uruguay", "Uruguai")),
    ("world-cup-wales", "País de Gales", ("Wales", "País de Gales")),
    ("world-cup-yugoslavia", "Iugoslávia", ("Yugoslavia", "Iugoslávia")),
    ("world-cup-zaire", "Zaire", ("Zaire",)),
)

WORLD_CUP_CANONICAL_DISPLAY_TEAMS = {
    alias.casefold(): {
        "display_team_id": display_team_id,
        "display_team_name": display_team_name,
    }
    for display_team_id, display_team_name, aliases in WORLD_CUP_CANONICAL_TEAM_VARIANTS
    for alias in aliases
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


def build_world_cup_edition_name(season_label: str) -> str:
    return f"Copa do Mundo FIFA {season_label}"
