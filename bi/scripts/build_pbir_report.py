"""Generate the versionable PBIR pages from a small, explicit specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "bi" / "FootballAnalytics_DesempenhoCompetitivo.Report" / "definition" / "pages"
VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
MOBILE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainerMobileState/2.4.0/schema.json"
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


def card(page: str, key: str, measures: list[str], x: int, y: int, width: int, height: int, order: int, value_size: int | None = None) -> dict:
    name = object_id(f"{page}:{key}")
    value_properties = {"fontColor": {"solid": {"color": literal(repr(PRIMARY))}}, "fontFamily": literal(repr("Segoe UI Semibold"))}
    if value_size:
        value_properties["fontSize"] = literal(f"{value_size}D")
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": position(x, y, width, height, order),
        "visual": {
            "visualType": "cardVisual",
            "query": {"queryState": {"Data": {"projections": [measure(item) for item in measures]}}},
            "objects": {
                "layout": [{"properties": {"backgroundShow": literal("true"), "paddingUniform": literal("10D"), "cellPadding": literal("8D")}, "selector": {"id": "default"}}],
                "value": [{"properties": value_properties, "selector": {"id": "default"}}],
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


def chart(page: str, key: str, visual_type: str, title: str, category: tuple[str, str], measures: list[str], x: int, y: int, width: int, height: int, order: int, series: tuple[str, str] | None = None, tooltips: list[str] | None = None) -> dict:
    name = object_id(f"{page}:{key}")
    query_state = {
        "Category": {"projections": [column(*category)]},
        "Y": {"projections": [measure(item) for item in measures]},
    }
    if series:
        query_state["Series"] = {"projections": [column(*series)]}
    if tooltips:
        query_state["Tooltips"] = {"projections": [measure(item) for item in tooltips]}
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


def mobile_positions(visuals: list[dict]) -> dict[str, dict]:
    positions: dict[str, dict] = {}
    y = 0
    slicer_column = 0

    for visual in sorted(visuals, key=lambda item: item["position"]["tabOrder"]):
        desktop = visual["position"]
        visual_type = visual["visual"]["visualType"]

        if visual_type == "textbox" and desktop["y"] == 12:
            continue

        if visual_type == "textbox":
            height = 42 if desktop["y"] < 30 else 34
            positions[visual["name"]] = {"x": 10, "y": y, "z": desktop["z"], "width": 300, "height": height, "tabOrder": desktop["tabOrder"]}
            y += height + 6
            continue

        if visual_type == "slicer":
            x = 10 if slicer_column == 0 else 165
            positions[visual["name"]] = {"x": x, "y": y, "z": desktop["z"], "width": 145, "height": 68, "tabOrder": desktop["tabOrder"]}
            slicer_column += 1
            if slicer_column == 2:
                slicer_column = 0
                y += 74
            continue

        if slicer_column:
            slicer_column = 0
            y += 74

        if visual_type == "cardVisual":
            projections = visual["visual"].get("query", {}).get("queryState", {}).get("Data", {}).get("projections", [])
            if len(projections) > 1:
                continue
            height = 120
        else:
            height = 390 if visual_type == "tableEx" else 280
        positions[visual["name"]] = {"x": 10, "y": y, "z": desktop["z"], "width": 300, "height": height, "tabOrder": desktop["tabOrder"]}
        y += height + 10

    return positions


def drillthrough_binding(name: str, table: str, field: str) -> dict:
    filter_name = f"{name}Filter"
    field_expr = {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": field}}
    return {
        "visibility": "HiddenInViewMode",
        "filterConfig": {
            "filters": [{
                "name": filter_name,
                "field": field_expr,
                "type": "Categorical",
                "howCreated": "Drillthrough",
            }],
        },
        "pageBinding": {
            "name": name,
            "type": "Drillthrough",
            "parameters": [{
                "name": f"{table}.{field}",
                "boundFilter": filter_name,
                "fieldExpr": field_expr,
            }],
        },
    }


def add_alt_text(visual: dict, page_name: str) -> None:
    configuration = visual["visual"]
    visual_type = configuration["visualType"]
    if visual_type == "textbox":
        paragraphs = configuration.get("objects", {}).get("general", [{}])[0].get("properties", {}).get("paragraphs", [])
        text = " ".join(run.get("value", "") for paragraph in paragraphs for run in paragraph.get("textRuns", []))
    elif visual_type == "slicer":
        text = next(iter(configuration["query"]["queryState"]["Values"]["projections"]))["nativeQueryRef"]
    else:
        title = configuration.get("visualContainerObjects", {}).get("title", [{}])[0].get("properties", {}).get("text", {})
        text = title.get("expr", {}).get("Literal", {}).get("Value", "").strip("'")
        if not text and visual_type == "cardVisual":
            text = ", ".join(item["nativeQueryRef"] for item in configuration["query"]["queryState"]["Data"]["projections"])
    configuration.setdefault("visualContainerObjects", {}).setdefault("general", []).append(
        {"properties": {"altText": literal(repr(text or f"{page_name}: elemento visual"))}}
    )


def build_pages() -> list[tuple[str, str, list[dict]]]:
    executive = object_id("page:executive")
    panorama = "4a73f0c432e1b1f30d28"
    teams = object_id("page:teams")
    evolution = object_id("page:evolution")
    players = object_id("page:players")
    quality = object_id("page:quality")
    team_detail = object_id("page:team-detail")
    player_detail = object_id("page:player-detail")

    pages = [
        (executive, "1. Resumo executivo", [
            header_panel(executive),
            textbox(executive, "title", "Resumo executivo orientado à decisão", 40, 18, 1000, 30, 1, 21, "#FFFFFF"),
            textbox(executive, "subtitle", "O que aconteceu · onde · por que importa · ação possível · confiança", 40, 45, 1100, 18, 2, 11, MINT),
            *common_slicers(executive, True),
            card(executive, "kpis", ["Jogos do Time", "Pontos", "PPG", "PPG Últimos 5", "Delta Forma 5 Jogos", "Conversão de Finalizações %", "Cobertura Estatísticas de Time %"], 20, 152, 1240, 96, 30),
            card(executive, "what", ["Resumo - O que aconteceu"], 20, 260, 610, 100, 40, 12),
            card(executive, "where", ["Resumo - Onde"], 645, 260, 615, 100, 41, 12),
            card(executive, "why", ["Resumo - Por que importa"], 20, 372, 360, 130, 42, 11),
            card(executive, "action", ["Resumo - Ação sugerida"], 395, 372, 420, 130, 43, 11),
            card(executive, "confidence", ["Resumo - Confiança"], 830, 372, 430, 130, 44, 11),
            table(executive, "decision_table", "Base da decisão — selecione um único escopo; mínimo de 10 jogos", [("DimTeam", "Time"), "Jogos do Time", "Pontos", "PPG (10+ jogos)", "PPG Últimos 5", "Delta Forma 5 Jogos", "Conversão de Finalizações %", "Cobertura Estatísticas de Time %"], 20, 514, 1240, 186, 50, "PPG (10+ jogos)"),
        ]),
        (panorama, "2. Panorama", [
            header_panel(panorama),
            textbox(panorama, "title", "Panorama das competições", 40, 18, 900, 30, 1, 21, "#FFFFFF"),
            textbox(panorama, "subtitle", "Projeto inteiro · filtre competição, temporada e período", 40, 45, 1000, 18, 2, 11, MINT),
            *common_slicers(panorama, False),
            card(panorama, "volume", ["Partidas", "Times", "Gols Totais", "Gols por Partida", "Cobertura de Placar %", "Dados disponíveis até"], 20, 152, 1240, 105, 30),
            card(panorama, "results", ["Vitórias Mandante", "Empates da Competição", "Vitórias Visitante", "Taxa Vitória Mandante %", "Taxa de Empates %", "Taxa Vitória Visitante %"], 20, 268, 1240, 105, 31),
            chart(panorama, "team_points", "clusteredBarChart", "Pontos por time no período", ("DimTeam", "Time"), ["Pontos"], 20, 385, 760, 315, 40, tooltips=["Jogos do Time", "PPG", "PPG Últimos 5"]),
            chart(panorama, "results_distribution", "clusteredColumnChart", "Distribuição de resultados", ("FactMatch", "Resultado"), ["Partidas"], 795, 385, 465, 315, 41),
        ]),
        (teams, "3. Times", [
            header_panel(teams),
            textbox(teams, "title", "Ranking e desempenho dos times", 40, 18, 900, 30, 1, 21, "#FFFFFF"),
            textbox(teams, "subtitle", "Clique com o botão direito em um time para abrir o detalhe · desempates oficiais não estão incluídos", 40, 45, 1150, 18, 2, 11, MINT),
            *common_slicers(teams, True),
            card(teams, "kpis", ["Jogos do Time", "Pontos", "PPG", "PPG Médio do Recorte", "Delta PPG vs Recorte", "Aproveitamento %"], 20, 152, 1240, 96, 30),
            table(teams, "ranking", "Ranking contextual: desempenho versus o recorte", [("DimTeam", "Time"), "Jogos do Time", "Pontos", "PPG", "PPG Médio do Recorte", "Delta PPG vs Recorte", "Percentil PPG", "Gols por Jogo do Time", "Conversão de Finalizações %", "Cobertura Estatísticas de Time %"], 20, 260, 790, 440, 40, "Pontos"),
            chart(teams, "points", "clusteredBarChart", "Pontos por time", ("DimTeam", "Time"), ["Pontos"], 825, 260, 435, 210, 41, tooltips=["Jogos do Time", "PPG", "PPG Últimos 5"]),
            chart(teams, "style", "clusteredBarChart", "Eficiência de finalização (95%+ de cobertura e 50+ chutes)", ("DimTeam", "Time"), ["Conversão de Finalizações %", "Precisão de Finalização %"], 825, 482, 435, 218, 42, tooltips=["Finalizações do Time", "Cobertura Estatísticas de Time %"]),
        ]),
        (evolution, "4. Evolução e mando", [
            header_panel(evolution),
            textbox(evolution, "title", "Evolução e efeito observado de mando", 40, 18, 1000, 30, 1, 21, "#FFFFFF"),
            textbox(evolution, "subtitle", "Selecione um time para leitura individual · múltiplos times formam o recorte agregado", 40, 45, 1100, 18, 2, 11, MINT),
            *common_slicers(evolution, True),
            card(evolution, "kpis", ["Pontos", "PPG", "PPG Últimos 5", "Delta Forma 5 Jogos", "PPG Casa", "PPG Fora", "Delta de Mando"], 20, 152, 1240, 96, 30),
            chart(evolution, "cumulative", "lineChart", "Pontos por ano no recorte", ("DimDate", "Ano"), ["Pontos"], 20, 260, 800, 440, 40, tooltips=["Jogos do Time", "PPG", "PPG Últimos 5"]),
            table(evolution, "venue", "Forma recente e efeito observado de mando", [("DimTeam", "Time"), "Jogos do Time", "PPG", "PPG Últimos 5", "Delta Forma 5 Jogos", "PPG Casa", "PPG Fora", "Delta de Mando (20+ jogos)"], 835, 260, 425, 440, 41, "Delta Forma 5 Jogos"),
        ]),
        (players, "5. Jogadores", [
            header_panel(players),
            textbox(players, "title", "Rankings de jogadores", 40, 18, 900, 30, 1, 21, "#FFFFFF"),
            textbox(players, "subtitle", "Clique com o botão direito em um jogador para abrir o detalhe · a cobertura varia conforme a fonte", 40, 45, 1150, 18, 2, 11, MINT),
            *common_slicers(players, True),
            card(players, "kpis", ["Gols", "Assistências", "Participações em Gol", "Cobertura de Minutos %", "Nota Média", "Cobertura de Nota %"], 20, 152, 1240, 96, 30),
            table(players, "ranking", "Produção e eficiência — métricas por 90 exigem 900+ minutos", [("DimPlayer", "Jogador"), ("DimTeam", "Time"), "Jogos do Jogador", "Minutos", "Gols", "Assistências", "Participações em Gol", "Gols por 90 (900+ min)", "Participações por 90 (900+ min)", "Precisão de Finalização do Jogador %", "Participação nos Gols do Time %", "Nota Média"], 20, 260, 800, 440, 40, "Participações em Gol"),
            chart(players, "goals_assists", "clusteredBarChart", "Participações em gol por 90 (mínimo de 900 minutos)", ("DimPlayer", "Jogador"), ["Participações por 90 (900+ min)"], 835, 260, 425, 440, 41, tooltips=["Minutos", "Jogos do Jogador", "Cobertura de Minutos %"]),
        ]),
        (quality, "6. Cobertura", [
            header_panel(quality),
            textbox(quality, "title", "Cobertura e confiabilidade do recorte", 40, 18, 1000, 30, 1, 21, "#FFFFFF"),
            textbox(quality, "subtitle", "Use esta página antes de comparar fontes, competições ou temporadas", 40, 45, 1100, 18, 2, 11, MINT),
            *common_slicers(quality, False),
            card(quality, "kpis", ["Escopos", "Partidas Declaradas", "Cobertura de Placar Declarada %", "Cobertura Estatísticas de Time %", "Cobertura de Nota %", "Cobertura de Minutos %"], 20, 152, 1240, 96, 30),
            table(quality, "matrix", "Matriz de cobertura por fonte, competição e temporada", [("DimScope", "provider"), ("DimScope", "competition"), ("DimScope", "season_label"), "Partidas Declaradas", "Cobertura de Placar Declarada %", "Cobertura de Jogadores Declarada %", "Escopos com Ranking de Jogadores"], 20, 260, 800, 440, 40, "Partidas Declaradas"),
            chart(quality, "coverage", "clusteredBarChart", "Cobertura declarada por competição", ("DimScope", "competition"), ["Cobertura de Placar Declarada %", "Cobertura de Jogadores Declarada %"], 835, 260, 425, 440, 41),
        ]),
        (team_detail, "Detalhe do time", [
            header_panel(team_detail),
            textbox(team_detail, "title", "Detalhe analítico do time", 40, 18, 1000, 30, 1, 21, "#FFFFFF"),
            textbox(team_detail, "subtitle", "Contexto recebido por drill-through · use Voltar para retornar ao ranking", 40, 45, 1100, 18, 2, 11, MINT),
            *common_slicers(team_detail, True),
            card(team_detail, "kpis", ["Jogos do Time", "Pontos", "PPG", "PPG Últimos 5", "Aproveitamento %", "Gols por Jogo do Time"], 20, 152, 1240, 96, 30),
            chart(team_detail, "evolution", "lineChart", "Evolução de pontos por ano", ("DimDate", "Ano"), ["Pontos"], 20, 260, 610, 280, 40),
            chart(team_detail, "efficiency", "clusteredBarChart", "Eficiência com cobertura suficiente", ("DimTeam", "Time"), ["Conversão de Finalizações %", "Precisão de Finalização %"], 645, 260, 615, 280, 41),
            table(team_detail, "venue", "Desempenho por mando", [("DimTeam", "Time"), "Jogos do Time", "PPG", "PPG Casa", "PPG Fora", "Delta de Mando (20+ jogos)"], 20, 552, 1240, 148, 42, "PPG"),
        ]),
        (player_detail, "Detalhe do jogador", [
            header_panel(player_detail),
            textbox(player_detail, "title", "Detalhe analítico do jogador", 40, 18, 1000, 30, 1, 21, "#FFFFFF"),
            textbox(player_detail, "subtitle", "Contexto recebido por drill-through · métricas por 90 exigem 900+ minutos", 40, 45, 1100, 18, 2, 11, MINT),
            *common_slicers(player_detail, True),
            card(player_detail, "kpis", ["Jogos do Jogador", "Minutos", "Gols", "Assistências", "Participações em Gol", "Nota Média"], 20, 152, 1240, 96, 30),
            chart(player_detail, "production", "clusteredColumnChart", "Participações em gol por ano", ("DimDate", "Ano"), ["Gols", "Assistências"], 20, 260, 610, 280, 40),
            chart(player_detail, "per90", "clusteredBarChart", "Produção por 90 com 900+ minutos", ("DimPlayer", "Jogador"), ["Gols por 90 (900+ min)", "Participações por 90 (900+ min)"], 645, 260, 615, 280, 41),
            table(player_detail, "summary", "Resumo do jogador no recorte", [("DimPlayer", "Jogador"), ("DimTeam", "Time"), "Jogos do Jogador", "Minutos", "Gols", "Assistências", "Precisão de Finalização do Jogador %", "Participação nos Gols do Time %", "Nota Média"], 20, 552, 1240, 148, 42, "Participações em Gol"),
        ]),
    ]
    return pages


def main() -> None:
    pages = build_pages()
    drillthrough_pages = {
        object_id("page:team-detail"): drillthrough_binding("DrillthroughTime", "DimTeam", "Time"),
        object_id("page:player-detail"): drillthrough_binding("DrillthroughJogador", "DimPlayer", "Jogador"),
    }
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
        page_definition.update(drillthrough_pages.get(page_name, {}))
        (page_dir / "page.json").write_text(json.dumps(page_definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        mobile = mobile_positions(visuals)
        for visual in visuals:
            add_alt_text(visual, display_name)
            visual_dir = page_dir / "visuals" / visual["name"]
            visual_dir.mkdir(parents=True, exist_ok=True)
            (visual_dir / "visual.json").write_text(json.dumps(visual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            mobile_file = visual_dir / "mobile.json"
            if visual["name"] in mobile:
                mobile_file.write_text(json.dumps({"$schema": MOBILE_SCHEMA, "position": mobile[visual["name"]]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            elif mobile_file.exists():
                mobile_file.unlink()

    order = [page_name for page_name, _, _ in pages]
    (PAGES / "pages.json").write_text(json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json", "pageOrder": order, "activePageName": order[0]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PBIR gerado: {len(pages)} páginas, {sum(len(items) for _, _, items in pages)} visuais")


if __name__ == "__main__":
    main()
