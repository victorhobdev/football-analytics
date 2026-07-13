"""Generate the versionable PBIR pages from a small, explicit specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "bi" / "FootballAnalytics_DesempenhoCompetitivo.Report" / "definition" / "pages"
VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
INK = "#111C2D"
MUTED = "#57657A"
PRIMARY = "#003526"
PRIMARY_STRONG = "#00513B"
MINT = "#8BD6B6"
SURFACE = "#F4F8F5"
CARD = "#FFFFFF"
BORDER = "#D8E3FB"


def object_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:20]


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def column(table: str, name: str) -> dict:
    return {
        "field": {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}},
        "queryRef": f"{table}.{name}",
        "nativeQueryRef": name,
    }


def measure(name: str) -> dict:
    return {
        "field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": name}},
        "queryRef": f"Medidas.{name}",
        "nativeQueryRef": name,
    }


def position(x: int, y: int, width: int, height: int, order: int) -> dict:
    return {"x": x, "y": y, "z": order, "height": height, "width": width, "tabOrder": order}


def title_objects(title: str) -> dict:
    return {
        "title": [{"properties": {
            "show": literal("true"),
            "text": literal(repr(title)),
            "fontColor": {"solid": {"color": literal(repr(INK))}},
            "fontFamily": literal(repr("Segoe UI Semibold")),
            "fontSize": literal("12D"),
            "alignment": literal(repr("left")),
        }}],
        "subTitle": [{"properties": {"show": literal("false")}}],
        "background": [{"properties": {"show": literal("true"), "color": {"solid": {"color": literal(repr(CARD))}}, "transparency": literal("0D")}}],
        "border": [{"properties": {"show": literal("true"), "color": {"solid": {"color": literal(repr(BORDER))}}, "radius": literal("12D")}}],
        "padding": [{"properties": {side: literal("10D") for side in ("top", "bottom", "left", "right")}}],
    }


def textbox(page: str, key: str, text: str, x: int, y: int, width: int, height: int, order: int, size: int = 24, color: str = INK) -> dict:
    name = object_id(f"{page}:{key}")
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, order),
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": text, "textStyle": {"fontFamily": "Segoe UI Semibold", "fontSize": f"{size}px", "color": color}}], "horizontalTextAlignment": "left"}]}}]},
            "visualContainerObjects": {
                "background": [{"properties": {"show": literal("false")}}],
                "border": [{"properties": {"show": literal("false")}}],
                "padding": [{"properties": {side: literal("0D") for side in ("top", "bottom", "left", "right")}}],
            },
        },
    }


def header_panel(page: str) -> dict:
    visual = textbox(page, "header_panel", "", 20, 12, 1240, 58, 0, 1, PRIMARY)
    visual["visual"]["visualContainerObjects"] = {
        "background": [{"properties": {"show": literal("true"), "color": {"solid": {"color": literal(repr(PRIMARY))}}, "transparency": literal("0D")}}],
        "border": [{"properties": {"show": literal("false"), "radius": literal("16D")}}],
        "padding": [{"properties": {side: literal("0D") for side in ("top", "bottom", "left", "right")}}],
    }
    return visual


def slicer(page: str, key: str, label: str, table: str, field: str, x: int, width: int, order: int, mode: str = "Dropdown") -> dict:
    name = object_id(f"{page}:{key}")
    visual = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [column(table, field)]}}},
        "objects": {
            "data": [{"properties": {"mode": literal(repr(mode))}}],
            "header": [{"properties": {
                "show": literal("true"),
                "text": literal(repr(label)),
                "fontColor": {"solid": {"color": literal(repr(MUTED))}},
                "textSize": literal("10D"),
            }}],
        },
        "visualContainerObjects": {
            "background": [{"properties": {"show": literal("true"), "color": {"solid": {"color": literal(repr(CARD))}}, "transparency": literal("0D")}}],
            "border": [{"properties": {"show": literal("true"), "color": {"solid": {"color": literal(repr(BORDER))}}, "radius": literal("10D")}}],
            "padding": [{"properties": {side: literal("7D") for side in ("top", "bottom", "left", "right")}}],
        },
        "syncGroup": {"groupName": f"Sync_{key}", "fieldChanges": True, "filterChanges": True},
    }
    return {"$schema": VISUAL_SCHEMA, "name": name, "position": position(x, 78, width, 66, order), "visual": visual}


def card(page: str, key: str, measures: list[str], x: int, y: int, width: int, height: int, order: int) -> dict:
    name = object_id(f"{page}:{key}")
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, order),
        "visual": {
            "visualType": "cardVisual",
            "query": {"queryState": {"Data": {"projections": [measure(item) for item in measures]}}},
            "objects": {
                "layout": [{"properties": {"backgroundShow": literal("true"), "paddingUniform": literal("10D"), "cellPadding": literal("8D")}, "selector": {"id": "default"}}],
                "value": [{"properties": {"fontColor": {"solid": {"color": literal(repr(PRIMARY))}}, "fontFamily": literal(repr("Segoe UI Semibold"))}, "selector": {"id": "default"}}],
                "label": [{"properties": {"fontColor": {"solid": {"color": literal(repr(MUTED))}}, "position": literal(repr("belowValue"))}, "selector": {"id": "default"}}],
                "shapeCustomRectangle": [{"properties": {"tileShape": literal(repr("rectangleRoundedByPixel")), "rectangleRoundedCurve": literal("12D")}, "selector": {"id": "default"}}],
                "outline": [{"properties": {"lineColor": {"solid": {"color": literal(repr(BORDER))}}}, "selector": {"id": "default"}}],
            },
            "visualContainerObjects": {
                "background": [{"properties": {"show": literal("false")}}],
                "border": [{"properties": {"show": literal("false")}}],
            },
        },
    }


def chart(page: str, key: str, visual_type: str, title: str, category: tuple[str, str], measures: list[str], x: int, y: int, width: int, height: int, order: int, series: tuple[str, str] | None = None) -> dict:
    name = object_id(f"{page}:{key}")
    query_state = {
        "Category": {"projections": [column(*category)]},
        "Y": {"projections": [measure(item) for item in measures]},
    }
    if series:
        query_state["Series"] = {"projections": [column(*series)]}
    objects = {
        "categoryAxis": [{"properties": {"labelColor": {"solid": {"color": literal(repr(MUTED))}}, "titleColor": {"solid": {"color": literal(repr(INK))}}, "gridlineStyle": literal(repr("dotted"))}}],
        "valueAxis": [{"properties": {"labelColor": {"solid": {"color": literal(repr(MUTED))}}, "titleColor": {"solid": {"color": literal(repr(INK))}}, "gridlineColor": {"solid": {"color": literal(repr(BORDER))}}, "gridlineStyle": literal(repr("dotted"))}}],
        "legend": [{"properties": {"labelColor": {"solid": {"color": literal(repr(MUTED))}}}}],
    }
    if len(measures) == 1:
        objects["dataPoint"] = [{"properties": {"defaultColor": {"solid": {"color": literal(repr(PRIMARY_STRONG))}}}}]
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, order),
        "visual": {
            "visualType": visual_type,
            "query": {"queryState": query_state, "sortDefinition": {"sort": [{"field": measure(measures[0])["field"], "direction": "Descending"}], "isDefaultSort": True}},
            "objects": objects,
            "visualContainerObjects": title_objects(title),
        },
    }


def table(page: str, key: str, title: str, fields: list[tuple[str, str] | str], x: int, y: int, width: int, height: int, order: int, sort_measure: str) -> dict:
    name = object_id(f"{page}:{key}")
    projections = [measure(item) if isinstance(item, str) else column(*item) for item in fields]
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, order),
        "visual": {
            "visualType": "tableEx",
            "query": {
                "queryState": {"Values": {"projections": projections}},
                "sortDefinition": {"sort": [{"field": measure(sort_measure)["field"], "direction": "Descending"}], "isDefaultSort": True},
            },
            "objects": {
                "columnHeaders": [{"properties": {
                    "columnAdjustment": literal("'growToFit'"),
                    "autoSizeColumnWidth": literal("true"),
                    "fontColor": {"solid": {"color": literal(repr(PRIMARY))}},
                    "backColor": {"solid": {"color": literal(repr(SURFACE))}},
                    "fontFamily": literal(repr("Segoe UI Semibold")),
                }}],
                "values": [{"properties": {
                    "fontColorPrimary": {"solid": {"color": literal(repr(INK))}},
                    "backColorPrimary": {"solid": {"color": literal(repr(CARD))}},
                    "backColorSecondary": {"solid": {"color": literal("'#F8FBF9'")}},
                }}],
                "grid": [{"properties": {"gridColor": {"solid": {"color": literal(repr(BORDER))}}, "rowPadding": literal("7D")}}],
                "total": [{"properties": {"fontColor": {"solid": {"color": literal(repr(PRIMARY))}}, "backColor": {"solid": {"color": literal("'#EAF5EF'")}}}}],
            },
            "visualContainerObjects": title_objects(title),
        },
    }


def common_slicers(page: str, include_team: bool) -> list[dict]:
    specs = [
        ("provider", "Fonte", "DimScope", "provider", 20, 150),
        ("competition", "Competição", "DimScope", "competition", 180, 280),
        ("season", "Temporada", "DimScope", "season_label", 470, 180),
        ("date", "Período", "DimDate", "date_day", 660, 250),
    ]
    if include_team:
        specs.append(("team", "Time", "DimTeam", "Time", 920, 340))
    else:
        specs[-1] = ("date", "Período", "DimDate", "date_day", 660, 600)
    return [slicer(page, *spec, order=10 + index, mode="Between" if spec[0] == "date" else "Dropdown") for index, spec in enumerate(specs)]


def build_pages() -> list[tuple[str, str, list[dict]]]:
    panorama = "4a73f0c432e1b1f30d28"
    teams = object_id("page:teams")
    evolution = object_id("page:evolution")
    players = object_id("page:players")
    quality = object_id("page:quality")

    pages = [
        (panorama, "1. Panorama", [
            header_panel(panorama),
            textbox(panorama, "title", "Panorama das competições", 40, 18, 900, 30, 1, 21, "#FFFFFF"),
            textbox(panorama, "subtitle", "Projeto inteiro · filtre competição, temporada e período", 40, 45, 1000, 18, 2, 11, MINT),
            *common_slicers(panorama, False),
            card(panorama, "volume", ["Partidas", "Times", "Gols Totais", "Gols por Partida", "Cobertura de Placar %", "Última Atualização"], 20, 152, 1240, 105, 30),
            card(panorama, "results", ["Vitórias Mandante", "Empates da Competição", "Vitórias Visitante", "Taxa Vitória Mandante %", "Taxa de Empates %", "Taxa Vitória Visitante %"], 20, 268, 1240, 105, 31),
            chart(panorama, "team_points", "clusteredBarChart", "Pontos por time no período", ("DimTeam", "Time"), ["Pontos"], 20, 385, 760, 315, 40),
            chart(panorama, "results_distribution", "clusteredColumnChart", "Distribuição de resultados", ("FactMatch", "Resultado"), ["Partidas"], 795, 385, 465, 315, 41),
        ]),
        (teams, "2. Times", [
            header_panel(teams),
            textbox(teams, "title", "Ranking e desempenho dos times", 40, 18, 900, 30, 1, 21, "#FFFFFF"),
            textbox(teams, "subtitle", "Leitura analítica · critérios oficiais de desempate não estão incluídos", 40, 45, 1000, 18, 2, 11, MINT),
            *common_slicers(teams, True),
            card(teams, "kpis", ["Jogos do Time", "Pontos", "PPG", "PPG Médio do Recorte", "Delta PPG vs Recorte", "Aproveitamento %"], 20, 152, 1240, 96, 30),
            table(teams, "ranking", "Ranking contextual: desempenho versus o recorte", [("DimTeam", "Time"), "Jogos do Time", "Pontos", "PPG", "PPG Médio do Recorte", "Delta PPG vs Recorte", "Percentil PPG", "Gols por Jogo do Time", "Conversão de Finalizações %", "Cobertura Estatísticas de Time %"], 20, 260, 790, 440, 40, "Pontos"),
            chart(teams, "points", "clusteredBarChart", "Pontos por time", ("DimTeam", "Time"), ["Pontos"], 825, 260, 435, 210, 41),
            chart(teams, "style", "clusteredBarChart", "Eficiência de finalização (95%+ de cobertura e 50+ chutes)", ("DimTeam", "Time"), ["Conversão de Finalizações %", "Precisão de Finalização %"], 825, 482, 435, 218, 42),
        ]),
        (evolution, "3. Evolução e mando", [
            header_panel(evolution),
            textbox(evolution, "title", "Evolução e efeito observado de mando", 40, 18, 1000, 30, 1, 21, "#FFFFFF"),
            textbox(evolution, "subtitle", "Selecione um time para leitura individual · múltiplos times formam o recorte agregado", 40, 45, 1100, 18, 2, 11, MINT),
            *common_slicers(evolution, True),
            card(evolution, "kpis", ["Pontos", "PPG", "PPG Últimos 5", "Delta Forma 5 Jogos", "PPG Casa", "PPG Fora", "Delta de Mando"], 20, 152, 1240, 96, 30),
            chart(evolution, "cumulative", "lineChart", "Pontos por ano no recorte", ("DimDate", "Ano"), ["Pontos"], 20, 260, 800, 440, 40),
            table(evolution, "venue", "Forma recente e efeito observado de mando", [("DimTeam", "Time"), "Jogos do Time", "PPG", "PPG Últimos 5", "Delta Forma 5 Jogos", "PPG Casa", "PPG Fora", "Delta de Mando (20+ jogos)"], 835, 260, 425, 440, 41, "Delta Forma 5 Jogos"),
        ]),
        (players, "4. Jogadores", [
            header_panel(players),
            textbox(players, "title", "Rankings de jogadores", 40, 18, 900, 30, 1, 21, "#FFFFFF"),
            textbox(players, "subtitle", "Produção, volume e nota · a cobertura varia conforme a fonte", 40, 45, 1000, 18, 2, 11, MINT),
            *common_slicers(players, True),
            card(players, "kpis", ["Gols", "Assistências", "Participações em Gol", "Cobertura de Minutos %", "Nota Média", "Cobertura de Nota %"], 20, 152, 1240, 96, 30),
            table(players, "ranking", "Produção e eficiência — métricas por 90 exigem 900+ minutos", [("DimPlayer", "Jogador"), ("DimTeam", "Time"), "Jogos do Jogador", "Minutos", "Gols", "Assistências", "Participações em Gol", "Gols por 90 (900+ min)", "Participações por 90 (900+ min)", "Precisão de Finalização do Jogador %", "Participação nos Gols do Time %", "Nota Média"], 20, 260, 800, 440, 40, "Participações em Gol"),
            chart(players, "goals_assists", "clusteredBarChart", "Participações em gol por 90 (mínimo de 900 minutos)", ("DimPlayer", "Jogador"), ["Participações por 90 (900+ min)"], 835, 260, 425, 440, 41),
        ]),
        (quality, "5. Cobertura", [
            header_panel(quality),
            textbox(quality, "title", "Cobertura e confiabilidade do recorte", 40, 18, 1000, 30, 1, 21, "#FFFFFF"),
            textbox(quality, "subtitle", "Use esta página antes de comparar fontes, competições ou temporadas", 40, 45, 1100, 18, 2, 11, MINT),
            *common_slicers(quality, False),
            card(quality, "kpis", ["Escopos", "Partidas Declaradas", "Cobertura de Placar Declarada %", "Cobertura Estatísticas de Time %", "Cobertura de Nota %", "Cobertura de Minutos %"], 20, 152, 1240, 96, 30),
            table(quality, "matrix", "Matriz de cobertura por fonte, competição e temporada", [("DimScope", "provider"), ("DimScope", "competition"), ("DimScope", "season_label"), "Partidas Declaradas", "Cobertura de Placar Declarada %", "Cobertura de Jogadores Declarada %", "Escopos com Ranking de Jogadores"], 20, 260, 800, 440, 40, "Partidas Declaradas"),
            chart(quality, "coverage", "clusteredBarChart", "Cobertura declarada por competição", ("DimScope", "competition"), ["Cobertura de Placar Declarada %", "Cobertura de Jogadores Declarada %"], 835, 260, 425, 440, 41),
        ]),
    ]
    return pages


def main() -> None:
    pages = build_pages()
    for page_name, display_name, visuals in pages:
        page_dir = PAGES / page_name
        page_dir.mkdir(parents=True, exist_ok=True)
        page_definition = {
            "$schema": PAGE_SCHEMA,
            "name": page_name,
            "displayName": display_name,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
            "objects": {
                "background": [{"properties": {"color": {"solid": {"color": literal(repr(SURFACE))}}, "transparency": literal("0D")}}],
                "outspace": [{"properties": {"color": {"solid": {"color": literal("'#E7EFEA'")}}}}],
            },
        }
        (page_dir / "page.json").write_text(json.dumps(page_definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for visual in visuals:
            visual_dir = page_dir / "visuals" / visual["name"]
            visual_dir.mkdir(parents=True, exist_ok=True)
            (visual_dir / "visual.json").write_text(json.dumps(visual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    order = [page_name for page_name, _, _ in pages]
    (PAGES / "pages.json").write_text(json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json", "pageOrder": order, "activePageName": order[0]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PBIR gerado: {len(pages)} páginas, {sum(len(items) for _, _, items in pages)} visuais")


if __name__ == "__main__":
    main()
