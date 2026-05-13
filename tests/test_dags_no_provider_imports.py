from __future__ import annotations

from pathlib import Path


def test_dags_do_not_import_concrete_providers_outside_registry():
    dag_dir = Path("infra/airflow/dags")
    forbidden_patterns = (
        "from src.providers.apifootball import",
        "from src.providers.sportmonks import",
        "from common.providers.api_football import",
        "from common.providers.sportmonks import",
        "APIFootballProvider(",
        "SportMonksProvider(",
    )
    offenders: list[str] = []

    for dag_file in dag_dir.rglob("*.py"):
        normalized = dag_file.as_posix()
        if "/common/providers/" in normalized:
            continue
        content = dag_file.read_text(encoding="utf-8", errors="ignore")
        for pattern in forbidden_patterns:
            if pattern in content:
                offenders.append(f"{dag_file}: {pattern}")

    assert not offenders, (
        "DAGs e servicos de orquestracao nao devem acoplar provider concreto fora da registry. Ocorrencias: "
        f"{offenders}"
    )
