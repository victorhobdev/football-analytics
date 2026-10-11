from datetime import date

from ..db.client import db_client


def resolve_legacy_team_ids(team_ids: list[str], season_label: str | None) -> dict[str, str]:
    if not team_ids:
        return {}

    year = (season_label or "").split("/")[0].split("_")[0]
    reference_date = date(int(year), 7, 1) if len(year) == 4 and year.isdigit() and int(year) > 0 else None
    rows = db_client.fetch_all(
        """
        select distinct p.source_id, p.canonical_id
        from raw.provider_entity_map p
        join mart.dim_team t on t.team_id::text = p.canonical_id
        where p.provider = 'legacy_dim_team'
          and p.entity_type = 'team'
          and p.mapping_state = 'approved'
          and p.source_id = any(%s::text[])
          and (p.valid_from is null or p.valid_from <= %s::date)
          and (p.valid_to is null or %s::date < p.valid_to);
        """,
        [team_ids, reference_date, reference_date],
    )
    candidates: dict[str, set[str]] = {}
    for row in rows:
        candidates.setdefault(str(row["source_id"]), set()).add(str(row["canonical_id"]))
    return {source_id: next(iter(ids)) for source_id, ids in candidates.items() if len(ids) == 1}
