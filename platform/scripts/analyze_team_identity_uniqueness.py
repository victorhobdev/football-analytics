"""Estimate unique clubs from source keys, match evidence, and reviewed exceptions.

Read-only analysis. It does not update the canonical registry or any mart.
"""

from __future__ import annotations

import collections
from difflib import SequenceMatcher

import psycopg
from psycopg.rows import dict_row

from build_team_match_fingerprint_candidates import build_edges, load_rows, normalize_name


COUNTRY_BY_COMPETITION = {
    "argentina_primera_division": "Argentina",
    "austrian_bundesliga": "Austria",
    "belgian_pro_league": "Belgium",
    "brasileirao_a": "Brazil",
    "brasileirao_b": "Brazil",
    "bundesliga": "Germany",
    "bundesliga_2": "Germany",
    "chinese_super_league": "China",
    # football-data.co.uk division EC is the English Conference.
    "copa_america_ec": "England",
    "copa_del_rey": "Spain",
    "copa_do_brasil": "Brazil",
    "danish_superliga": "Denmark",
    "efl_championship": "England",
    "efl_league_one": "England",
    "efl_league_two": "England",
    "eredivisie": "Netherlands",
    "fa_womens_super_league": "England",
    "finnish_veikkausliiga": "Finland",
    "frauen_bundesliga": "Germany",
    "greek_super_league": "Greece",
    "indian_super_league": "India",
    "j1_league": "Japan",
    "la_liga": "Spain",
    "league_of_ireland": "Ireland",
    "liga_f": "Spain",
    "liga_mx": "Mexico",
    "liga_profesional_argentina": "Argentina",
    "ligue_1": "France",
    "ligue_2": "France",
    "major_league_soccer": "United States",
    "north_american_league": "United States",
    "norwegian_eliteserien": "Norway",
    "nwsl": "United States",
    "polish_ekstraklasa": "Poland",
    "premier_league": "England",
    "primeira_liga": "Portugal",
    "romanian_superliga": "Romania",
    "russian_premier_league": "Russia",
    "scottish_championship": "Scotland",
    "scottish_league_one": "Scotland",
    "scottish_league_two": "Scotland",
    "scottish_premiership": "Scotland",
    "segunda_division": "Spain",
    "serie_a_it": "Italy",
    "serie_a_women": "Italy",
    "serie_b_it": "Italy",
    "super_lig_turkey": "Turkey",
    "supercopa_do_brasil": "Brazil",
    "swedish_allsvenskan": "Sweden",
    "swiss_super_league": "Switzerland",
}
WOMENS_COMPETITIONS = {
    "fa_womens_super_league",
    "fifa_womens_world_cup",
    "frauen_bundesliga",
    "liga_f",
    "nwsl",
    "serie_a_women",
    "uefa_womens_euro",
}
NATIONAL_COMPETITIONS = {
    "african_cup_of_nations",
    "copa_america",
    "fifa_u20_world_cup",
    "fifa_womens_world_cup",
    "uefa_euro",
    "uefa_womens_euro",
}
BELENENSES_IDS = {1002633571734, 1025187804228, 1030245672235}
RESEARCHED_MERGES = (
    (1024, 1048633958805, "transfermarkt club 614 / CR Flamengo"),
    (962323330062, 1006002478307, "Evian/Thonon historical club"),
    (973475021256, 988912771680, "Desportivo Aves/Aves historical club"),
    (354, 967981353920, "Malmö/Malmo transliteration"),
    (2921, 967537389444, "UD Las Palmas abbreviation"),
    (964789114291, 1048261083566, "D.C. United punctuation"),
    (44, 910000000147, "Olympique de Marseille name variant"),
    (1001218452069, 1041808252480, "HamKam punctuation"),
    (1000849291562, 1055922937070, "Preußen Münster transliteration"),
    (1011393242579, 1053099063981, "Östers IF / Öster"),
    (1658, 1006756843376, "Portimonense professional team/SAD label"),
    (2927, 1033028897283, "Arminia Bielefeld legal-name variant"),
    (910000000872, 977715359738, "SV Darmstadt 98 abbreviation"),
    (910000000872, 1048217669527, "Darmstadt abbreviation"),
    (966572301434, 979878180561, "Atlanta United abbreviation"),
    (984130323872, 1030271575872, "AFC Telford rows after 2004 reformation"),
    (974124444176, 1039660198758, "FC Ingolstadt 04 abbreviation"),
    (967360854602, 986571674023, "FK Krasnodar abbreviation"),
    (975975985230, 1040108336691, "SC Beira-Mar punctuation"),
    (976051894429, 1050334040580, "CS Universitatea Craiova abbreviation"),
    (1008714379910, 1008904925322, "SC Olhanense abbreviation"),
    (12152, 989403871480, "current Club Football Estrela da Amadora"),
    (3427, 1022352308494, "Clube Atlético Mineiro legal name"),
    (997588959080, 1043278459436, "CF União Madeira legal name"),
    (997155629425, 1012397576828, "Huddersfield Town abbreviation"),
    (975825545058, 1007386557379, "AC Ajaccio abbreviation"),
    (1036456282912, 1051954043286, "UD Almería abbreviation"),
    (1011755173677, 1040518362249, "Greuther Fürth transliteration"),
    (962541868419, 964136912774, "SC Farense abbreviation"),
    (2864, 986270877059, "Botafogo de Futebol e Regatas/RJ label"),
)
EXACT_NAME_EXCEPTIONS = {
    "Apollon",
    "Athletic Club",
    "Boavista",
    "Everton",
    "Liverpool",
    "Nacional",
    "Peñarol",
    "Portuguesa",
    "Universidad Católica",
}


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[int, int] = {}
        self.applied = collections.Counter()

    def find(self, value: int) -> int:
        self.parent.setdefault(value, value)
        if self.parent[value] != value:
            self.parent[value] = self.find(self.parent[value])
        return self.parent[value]

    def union(self, left: int, right: int, reason: str) -> bool:
        left_root, right_root = self.find(left), self.find(right)
        if left_root == right_root:
            return False
        self.parent[right_root] = left_root
        self.applied[reason] += 1
        return True


RESOLUTION_RESULT: dict[str, object] = {}


def main() -> None:
    union = UnionFind()
    with psycopg.connect(
        "postgresql://football:football@127.0.0.1:5432/football_dw",
        row_factory=dict_row,
    ) as conn:
        rows = load_rows(conn)
        names = {
            int(row["team_id"]): row["team_name"]
            for row in conn.execute("select team_id, team_name from mart.dim_team")
        }
        features = {
            team_id: {
                "sources": set(),
                "countries": set(),
                "genders": set(),
                "types": set(),
            }
            for team_id in names
        }
        for row in rows:
            feature = features[int(row["team_id"])]
            competition = row["competition_key"]
            source = row["source"]
            feature["sources"].add(source)
            if source == "statsbomb_open_data":
                continue
            feature["genders"].add(
                "female" if competition in WOMENS_COMPETITIONS else "male"
            )
            feature["types"].add(
                "national"
                if source == "fjelstul_worldcup" or competition in NATIONAL_COMPETITIONS
                else "club"
            )
            if competition in COUNTRY_BY_COMPETITION:
                feature["countries"].add(COUNTRY_BY_COMPETITION[competition])

        statsbomb_teams = conn.execute(
            """
            with sides as (
                select home_team_id as source_team_id, competition_id, season_id,
                       canonical_competition_key as competition_key
                from raw.statsbomb_matches
                union
                select away_team_id, competition_id, season_id, canonical_competition_key
                from raw.statsbomb_matches
            )
            select s.source_team_id, s.competition_key,
                   c.competition_gender, c.competition_international, c.country_name
            from sides s
            left join raw.statsbomb_competition_seasons c
              on c.competition_id = s.competition_id
             and c.season_id = s.season_id
            """
        ).fetchall()
        for row in statsbomb_teams:
            team_id = 910000000000 + int(row["source_team_id"])
            if team_id not in features:
                continue
            competition = row["competition_key"]
            feature = features[team_id]
            feature["sources"].add("statsbomb_open_data")
            feature["genders"].add(
                "female"
                if row["competition_gender"] == "female"
                or competition in WOMENS_COMPETITIONS
                else "male"
            )
            feature["types"].add(
                "national"
                if row["competition_international"] or competition in NATIONAL_COMPETITIONS
                else "club"
            )
            if row["country_name"] and not row["competition_international"]:
                feature["countries"].add(row["country_name"])
            elif competition in COUNTRY_BY_COMPETITION:
                feature["countries"].add(COUNTRY_BY_COMPETITION[competition])

        transfermarkt = conn.execute(
            """
            with sides as (
                select s.home_team_id as team_id, g.home_club_id as club_id
                from mart.stg_matches s
                join raw.tm_games g
                  on g.game_id::bigint = s.fixture_id - 930000000000
                where coalesce(s.source_provider, s.provider) = 'transfermarkt'
                union all
                select s.away_team_id, g.away_club_id
                from mart.stg_matches s
                join raw.tm_games g
                  on g.game_id::bigint = s.fixture_id - 930000000000
                where coalesce(s.source_provider, s.provider) = 'transfermarkt'
            ), source_ids as (
                select team_id, min(club_id) as club_id
                from sides
                group by team_id
                having count(distinct club_id) = 1
            )
            select s.team_id, s.club_id, max(c.country_name) as country
            from source_ids s
            left join raw.tm_clubs club on club.club_id = s.club_id
            left join raw.tm_competitions c
              on c.competition_id = club.domestic_competition_id
            group by s.team_id, s.club_id
            """
        ).fetchall()

    transfermarkt_by_club: dict[str, list[int]] = collections.defaultdict(list)
    for row in transfermarkt:
        team_id = int(row["team_id"])
        transfermarkt_by_club[row["club_id"]].append(team_id)
        if row["country"]:
            features[team_id]["countries"].add(row["country"])

    for left, right in build_edges(rows):
        if left in BELENENSES_IDS or right in BELENENSES_IDS:
            continue
        union.union(left, right, "match_fingerprint")
    for team_ids in transfermarkt_by_club.values():
        for team_id in team_ids[1:]:
            union.union(team_ids[0], team_id, "transfermarkt_club_id")

    elo_by_name_country: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    for team_id, name in names.items():
        if "eloratings" not in features[team_id]["sources"]:
            continue
        for country in features[team_id]["countries"]:
            elo_by_name_country[(name, country)].append(team_id)
    for team_ids in elo_by_name_country.values():
        for team_id in team_ids[1:]:
            union.union(team_ids[0], team_id, "elo_same_name_country")

    changed = True
    while changed:
        changed = False
        components: dict[int, list[int]] = collections.defaultdict(list)
        for team_id in names:
            components[union.find(team_id)].append(team_id)
        roots_by_name: dict[str, set[int]] = collections.defaultdict(set)
        for team_id, name in names.items():
            roots_by_name[name].add(union.find(team_id))
        components_by_name = {
            name: [components[root] for root in roots]
            for name, roots in roots_by_name.items()
        }
        for groups in components_by_name.values():
            for index, left_ids in enumerate(groups):
                for right_ids in groups[index + 1 :]:
                    left_country = set().union(
                        *(features[value]["countries"] for value in left_ids)
                    )
                    right_country = set().union(
                        *(features[value]["countries"] for value in right_ids)
                    )
                    left_gender = set().union(
                        *(features[value]["genders"] for value in left_ids)
                    )
                    right_gender = set().union(
                        *(features[value]["genders"] for value in right_ids)
                    )
                    left_type = set().union(
                        *(features[value]["types"] for value in left_ids)
                    )
                    right_type = set().union(
                        *(features[value]["types"] for value in right_ids)
                    )
                    same_context = bool(left_country & right_country)
                    same_national_team = "national" in left_type and "national" in right_type
                    if (
                        (same_context or same_national_team)
                        and bool(left_gender & right_gender)
                        and bool(left_type & right_type)
                        and union.union(left_ids[0], right_ids[0], "exact_name_context")
                    ):
                        changed = True

    for left, right, evidence in RESEARCHED_MERGES:
        union.union(left, right, f"web_research: {evidence}")

    # Remaining exact-name pairs were reviewed against UEFA/CONMEBOL context.
    # Merge only compatible type/gender and never cross a known country conflict.
    exact_groups: dict[str, list[int]] = collections.defaultdict(list)
    for team_id, name in names.items():
        exact_groups[name].append(team_id)
    for name, team_ids in exact_groups.items():
        if name in EXACT_NAME_EXCEPTIONS:
            continue
        for index, left in enumerate(team_ids):
            for right in team_ids[index + 1 :]:
                if union.find(left) == union.find(right):
                    continue
                left_feature, right_feature = features[left], features[right]
                if not (left_feature["genders"] & right_feature["genders"]):
                    continue
                if not (left_feature["types"] & right_feature["types"]):
                    continue
                if (
                    left_feature["countries"]
                    and right_feature["countries"]
                    and not (left_feature["countries"] & right_feature["countries"])
                ):
                    continue
                union.union(left, right, "reviewed_exact_name")

    normalized_exceptions = {normalize_name(value) for value in EXACT_NAME_EXCEPTIONS}
    changed = True
    while changed:
        changed = False
        normalized_components: dict[str, dict[int, list[int]]] = collections.defaultdict(
            lambda: collections.defaultdict(list)
        )
        for team_id, name in names.items():
            normalized_components[normalize_name(name)][union.find(team_id)].append(team_id)
        for normalized, grouped in normalized_components.items():
            if not normalized or normalized in normalized_exceptions:
                continue
            components = list(grouped.values())
            for index, left_ids in enumerate(components):
                for right_ids in components[index + 1 :]:
                    left_countries = set().union(
                        *(features[value]["countries"] for value in left_ids)
                    )
                    right_countries = set().union(
                        *(features[value]["countries"] for value in right_ids)
                    )
                    left_genders = set().union(
                        *(features[value]["genders"] for value in left_ids)
                    )
                    right_genders = set().union(
                        *(features[value]["genders"] for value in right_ids)
                    )
                    left_types = set().union(
                        *(features[value]["types"] for value in left_ids)
                    )
                    right_types = set().union(
                        *(features[value]["types"] for value in right_ids)
                    )
                    if not (left_countries & right_countries):
                        continue
                    if not (left_genders & right_genders) or not (left_types & right_types):
                        continue
                    if union.union(
                        left_ids[0], right_ids[0], "normalized_name_context"
                    ):
                        changed = True

    roots = {union.find(team_id) for team_id in names}
    belenenses_roots = {
        union.find(team_id) for team_id in BELENENSES_IDS if team_id in names
    }
    # The mixed Elo key is split into the club and the SAD.  The two native
    # Transfermarkt keys identify those same two referents, so the three
    # legacy rows collapse to two canonical identities (not four).
    unique_high_confidence = len(roots - belenenses_roots) + 2
    unresolved_exact: dict[str, set[int]] = collections.defaultdict(set)
    for team_id, name in names.items():
        unresolved_exact[name].add(union.find(team_id))
    unresolved_exact = {
        name: roots for name, roots in unresolved_exact.items() if len(roots) > 1
    }
    global RESOLUTION_RESULT
    RESOLUTION_RESULT = {
        "names": names,
        "features": features,
        "union": union,
        "roots": roots,
        "belenenses_roots": belenenses_roots,
    }
    print(
        {
            "legacy_rows": len(names),
            "unique_high_confidence": unique_high_confidence,
            "confirmed_reductions": len(names) - unique_high_confidence,
            "contextual_splits": 1,
            "unresolved_exact_groups": len(unresolved_exact),
            "unresolved_exact_potential_reductions": sum(
                len(group) - 1 for group in unresolved_exact.values()
            ),
            "applied_edges": dict(union.applied),
        }
    )

    components: dict[int, list[int]] = collections.defaultdict(list)
    for team_id in names:
        components[union.find(team_id)].append(team_id)
    fuzzy_candidates = []
    component_items = list(components.items())
    for index, (left_root, left_ids) in enumerate(component_items):
        left_names = {names[value] for value in left_ids}
        left_countries = set().union(
            *(features[value]["countries"] for value in left_ids)
        )
        left_genders = set().union(*(features[value]["genders"] for value in left_ids))
        left_types = set().union(*(features[value]["types"] for value in left_ids))
        for right_root, right_ids in component_items[index + 1 :]:
            right_countries = set().union(
                *(features[value]["countries"] for value in right_ids)
            )
            if not left_countries or not right_countries:
                continue
            if not (left_countries & right_countries):
                continue
            right_genders = set().union(
                *(features[value]["genders"] for value in right_ids)
            )
            right_types = set().union(*(features[value]["types"] for value in right_ids))
            if not (left_genders & right_genders) or not (left_types & right_types):
                continue
            right_names = {names[value] for value in right_ids}
            best = max(
                (
                    SequenceMatcher(None, normalize_name(left), normalize_name(right)).ratio(),
                    left,
                    right,
                )
                for left in left_names
                for right in right_names
            )
            if best[0] >= 0.82:
                fuzzy_candidates.append(
                    {
                        "score": round(best[0], 3),
                        "left_root": left_root,
                        "right_root": right_root,
                        "left_name": best[1],
                        "right_name": best[2],
                        "countries": sorted(left_countries & right_countries),
                    }
                )
    print({"fuzzy_context_candidates": len(fuzzy_candidates)})
    RESOLUTION_RESULT["fuzzy_candidates"] = fuzzy_candidates
    for candidate in sorted(fuzzy_candidates, key=lambda value: -value["score"]):
        print(candidate)
    for name, component_roots in sorted(unresolved_exact.items()):
        members = [
            {
                "team_id": team_id,
                "sources": sorted(features[team_id]["sources"]),
                "countries": sorted(features[team_id]["countries"]),
                "genders": sorted(features[team_id]["genders"]),
            }
            for team_id in sorted(names)
            if names[team_id] == name and union.find(team_id) in component_roots
        ]
        print({"unresolved_name": name, "members": members})


if __name__ == "__main__":
    main()
