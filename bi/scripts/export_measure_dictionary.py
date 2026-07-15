"""Generate the human-readable measure catalog from the executable TMDL."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "bi" / "FootballAnalytics_DesempenhoCompetitivo.SemanticModel" / "definition" / "tables" / "Medidas.tmdl"
OUTPUT = ROOT / "docs" / "bi" / "DICIONARIO_MEDIDAS.md"
MEASURE = re.compile(r"^\tmeasure ('.*?'|[^=]+?)\s*=")


def parse() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        match = MEASURE.match(line)
        if match:
            current = {"name": match.group(1).strip("'"), "folder": "Sem pasta", "format": "Texto"}
            records.append(current)
        elif current and line.startswith("\t\tdisplayFolder: "):
            current["folder"] = line.split(": ", 1)[1]
        elif current and line.startswith("\t\tformatString: "):
            current["format"] = line.split(": ", 1)[1]
        elif line.startswith("\tcolumn "):
            current = None
    return records


def main() -> None:
    measures = parse()
    lines = [
        "# Dicionário de medidas DAX",
        "",
        f"Catálogo gerado a partir do TMDL executável. **{len(measures)} medidas**; fórmulas completas em `bi/FootballAnalytics_DesempenhoCompetitivo.SemanticModel/definition/tables/Medidas.tmdl`.",
        "",
        "## Regras de negócio críticas",
        "",
        "- **PPG:** pontos divididos por jogos do time.",
        "- **PPG Últimos 5:** PPG dos cinco jogos mais recentes dentro do contexto filtrado.",
        "- **Conversão de Finalizações:** só aparece com 95%+ de cobertura, 50+ finalizações e gols não superiores às tentativas.",
        "- **Métricas por 90:** só aparecem com 900+ minutos.",
        "- **Percentil PPG:** posição relativa entre times do contexto selecionado; não é classificação oficial.",
        "- **Ausência:** valores sem cobertura permanecem nulos e não são convertidos em zero.",
        "",
    ]
    for folder in sorted({item["folder"] for item in measures}):
        lines.extend([f"## {folder}", "", "| Medida | Formato |", "| --- | --- |"])
        lines.extend(f"| {item['name']} | `{item['format']}` |" for item in measures if item["folder"] == folder)
        lines.append("")
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    assert len(measures) >= 70 and any(item["name"] == "Resumo - Ação sugerida" for item in measures)
    print(f"Medidas={len(measures)} catálogo={OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
