"""Reproduce the portfolio study: has home advantage declined since 2000?"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import psycopg
from dotenv import dotenv_values
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "analysis" / "home_advantage"
REPORT = ROOT / "docs" / "analysis" / "HOME_ADVANTAGE.md"
RNG_SEED = 20260712

QUERY = """
select competition_key, season, season_label, date_day, home_goals, away_goals
from mart.fact_matches
where provider = 'eloratings'
  and date_day >= date '2000-01-01'
  and date_day < date '2026-01-01'
  and home_goals is not null
  and away_goals is not null
"""


def load_matches() -> pd.DataFrame:
    env = dotenv_values(ROOT / ".env")
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname=env["POSTGRES_DB"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(QUERY)
            return pd.DataFrame(cursor.fetchall(), columns=[column.name for column in cursor.description])


def prepare(matches: pd.DataFrame) -> pd.DataFrame:
    frame = matches.copy()
    frame["year"] = pd.to_datetime(frame["date_day"]).dt.year
    frame["decade"] = frame["year"].floordiv(10).mul(10)
    frame["home_points"] = np.select(
        [frame.home_goals > frame.away_goals, frame.home_goals == frame.away_goals],
        [3, 1],
        default=0,
    )
    frame["away_points"] = np.select(
        [frame.away_goals > frame.home_goals, frame.home_goals == frame.away_goals],
        [3, 1],
        default=0,
    )
    frame["home_advantage_points"] = frame.home_points - frame.away_points
    frame["home_win"] = (frame.home_goals > frame.away_goals).astype(int)
    frame["draw"] = (frame.home_goals == frame.away_goals).astype(int)
    frame["away_win"] = (frame.home_goals < frame.away_goals).astype(int)
    return frame


def season_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby(["competition_key", "season", "season_label"], as_index=False)
        .agg(
            matches=("date_day", "size"),
            start_year=("year", "min"),
            home_ppg=("home_points", "mean"),
            away_ppg=("away_points", "mean"),
            home_advantage_ppg=("home_advantage_points", "mean"),
            home_win_rate=("home_win", "mean"),
            draw_rate=("draw", "mean"),
            away_win_rate=("away_win", "mean"),
            home_goals_per_match=("home_goals", "mean"),
            away_goals_per_match=("away_goals", "mean"),
        )
        .sort_values(["competition_key", "start_year"])
    )


def mean_ci(values: pd.Series) -> tuple[float, float, float]:
    clean = values.dropna().to_numpy(dtype=float)
    mean = float(clean.mean())
    margin = float(stats.t.ppf(0.975, len(clean) - 1) * stats.sem(clean))
    return mean, mean - margin, mean + margin


def hedges_g(first: np.ndarray, second: np.ndarray) -> float:
    n1, n2 = len(first), len(second)
    pooled = np.sqrt(((n1 - 1) * first.var(ddof=1) + (n2 - 1) * second.var(ddof=1)) / (n1 + n2 - 2))
    correction = 1 - 3 / (4 * (n1 + n2) - 9)
    return float(correction * (second.mean() - first.mean()) / pooled)


def fixed_effect_trend(seasons: pd.DataFrame, iterations: int = 4000) -> tuple[float, float, float, float, int, int]:
    eligible = seasons.groupby("competition_key").filter(lambda group: len(group) >= 5).copy()
    eligible["weighted_year"] = eligible.matches * eligible.start_year
    eligible["weighted_advantage"] = eligible.matches * eligible.home_advantage_ppg
    weight_sum = eligible.groupby("competition_key").matches.transform("sum")
    eligible["year_centered"] = eligible.start_year - eligible.groupby("competition_key").weighted_year.transform("sum") / weight_sum
    eligible["advantage_centered"] = eligible.home_advantage_ppg - eligible.groupby("competition_key").weighted_advantage.transform("sum") / weight_sum
    eligible["numerator"] = eligible.matches * eligible.year_centered * eligible.advantage_centered
    eligible["denominator"] = eligible.matches * eligible.year_centered.pow(2)
    sufficient = eligible.groupby("competition_key")[["numerator", "denominator"]].sum()
    observed = float(sufficient.numerator.sum() / sufficient.denominator.sum() * 10)
    rng = np.random.default_rng(RNG_SEED)
    chosen = rng.integers(0, len(sufficient), size=(iterations, len(sufficient)))
    numerators = sufficient.numerator.to_numpy()[chosen].sum(axis=1)
    denominators = sufficient.denominator.to_numpy()[chosen].sum(axis=1)
    boot = numerators / denominators * 10
    low, high = np.quantile(boot, [0.025, 0.975])
    p_value = 2 * min(float(np.mean(boot <= 0)), float(np.mean(boot >= 0)))
    return observed, float(low), float(high), p_value, eligible.competition_key.nunique(), len(eligible)


def period_comparison(seasons: pd.DataFrame) -> dict[str, float | int]:
    early = seasons.loc[seasons.start_year.between(2000, 2009), "home_advantage_ppg"].to_numpy()
    recent = seasons.loc[seasons.start_year.between(2020, 2025), "home_advantage_ppg"].to_numpy()
    test = stats.ttest_ind(early, recent, equal_var=False)
    rng = np.random.default_rng(RNG_SEED)
    differences = np.empty(10000)
    for index in range(len(differences)):
        differences[index] = rng.choice(recent, len(recent), replace=True).mean() - rng.choice(early, len(early), replace=True).mean()
    low, high = np.quantile(differences, [0.025, 0.975])
    return {
        "early_seasons": len(early),
        "recent_seasons": len(recent),
        "early_mean": float(early.mean()),
        "recent_mean": float(recent.mean()),
        "difference": float(recent.mean() - early.mean()),
        "ci_low": float(low),
        "ci_high": float(high),
        "p_value": float(test.pvalue),
        "hedges_g": hedges_g(early, recent),
    }


def decade_summary(frame: pd.DataFrame, seasons: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for decade, matches in frame.groupby("decade"):
        season_values = seasons.loc[seasons.start_year.floordiv(10).mul(10) == decade, "home_advantage_ppg"]
        mean, low, high = mean_ci(season_values)
        rows.append({
            "decade": decade,
            "matches": len(matches),
            "seasons": len(season_values),
            "competitions": matches.competition_key.nunique(),
            "home_goals_per_match": matches.home_goals.mean(),
            "away_goals_per_match": matches.away_goals.mean(),
            "home_win_rate": matches.home_win.mean(),
            "draw_rate": matches.draw.mean(),
            "away_win_rate": matches.away_win.mean(),
            "home_advantage_ppg": mean,
            "home_advantage_ci_low": low,
            "home_advantage_ci_high": high,
        })
    return pd.DataFrame(rows)


def effect_label(value: float) -> str:
    magnitude = abs(value)
    return "desprezível" if magnitude < 0.2 else "pequeno" if magnitude < 0.5 else "moderado" if magnitude < 0.8 else "grande"


def markdown_table(frame: pd.DataFrame) -> str:
    rendered = frame.copy()
    for name in rendered.select_dtypes(include="number"):
        rendered[name] = rendered[name].map(lambda value: f"{value:.3f}")
    header = "| " + " | ".join(rendered.columns) + " |"
    separator = "| " + " | ".join("---" for _ in rendered.columns) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in rendered.itertuples(index=False, name=None)]
    return "\n".join([header, separator, *rows])


def write_report(frame: pd.DataFrame, seasons: pd.DataFrame, decades: pd.DataFrame) -> None:
    comparison = period_comparison(seasons)
    trend, trend_low, trend_high, trend_p, competitions, observations = fixed_effect_trend(seasons)
    points = frame.home_points.value_counts(normalize=True).reindex([0, 1, 3], fill_value=0)
    goals = pd.cut(frame.home_goals + frame.away_goals, [-1, 0, 1, 2, 3, 4, np.inf], labels=["0", "1", "2", "3", "4", "5+"]).value_counts(normalize=True).sort_index()
    conclusion = (
        "há evidência de redução" if trend_high < 0 else
        "há evidência de aumento" if trend_low > 0 else
        "não há evidência conclusiva de mudança"
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# A vantagem de jogar em casa diminuiu?

## Resumo executivo

No recorte de **{len(frame):,} partidas**, **{len(seasons):,} temporadas** e **{frame.competition_key.nunique()} competições** do provedor `eloratings` entre 2000 e 2025, {conclusion}. O modelo com efeito fixo de competição estimou **{trend:+.3f} ponto de vantagem por década** (IC95% bootstrap **{trend_low:+.3f} a {trend_high:+.3f}**, p bootstrap = **{trend_p:.4f}**).

Comparando temporadas iniciadas em 2000–2009 com 2020–2025, a vantagem média passou de **{comparison['early_mean']:.3f}** para **{comparison['recent_mean']:.3f}** ponto por jogo: diferença de **{comparison['difference']:+.3f}** (IC95% bootstrap **{comparison['ci_low']:+.3f} a {comparison['ci_high']:+.3f}**, Welch p = **{comparison['p_value']:.4f}**, Hedges g = **{comparison['hedges_g']:+.3f}**, efeito {effect_label(float(comparison['hedges_g']))}).

**Decisão possível:** trate mando como variável contextual, não como bônus fixo. Para planejamento ou comparação entre times, use taxas específicas da competição e da temporada; a média histórica global esconde diferenças estruturais.

**Confiança:** moderada. O resultado controla diferenças permanentes entre competições e usa temporada como unidade, mas não controla força relativa dos times, público, viagens, estádio neutro ou mudanças regulatórias.

## Preparação e método

- Fonte: `mart.fact_matches`, somente `provider = 'eloratings'`, placares válidos e datas entre 2000 e 2025.
- Vantagem por partida: pontos do mandante menos pontos do visitante.
- Análise exploratória: gols, distribuição de pontos e resultados por década.
- Diferença entre períodos: teste t de Welch sobre médias de temporada, IC bootstrap e Hedges g.
- Controle: regressão ponderada por partidas após remoção da média de cada competição; IC e p-valor por bootstrap de competições.
- Unidade do modelo: competição–temporada; {competitions} competições elegíveis e {observations} temporadas com ao menos cinco temporadas por competição.

## Distribuições

| Resultado do mandante | Participação |
| --- | ---: |
| Derrota, 0 ponto | {points[0]:.2%} |
| Empate, 1 ponto | {points[1]:.2%} |
| Vitória, 3 pontos | {points[3]:.2%} |

| Gols totais na partida | Participação |
| --- | ---: |
{chr(10).join(f'| {label} | {value:.2%} |' for label, value in goals.items())}

## Evolução por década

{markdown_table(decades)}

## Limitações

- `eloratings` oferece amplitude histórica, mas a taxonomia contém competições de origens diferentes e não informa estádio neutro.
- A análise é observacional: associação temporal não prova causalidade.
- O efeito fixo controla diferenças persistentes entre competições, não mudanças específicas dentro de cada temporada.
- A comparação 2020–2025 inclui o período de estádios vazios; estudos causais exigiriam variável explícita de público e desenho próprio.
- Provedores não foram combinados para evitar duplicidade e escalas semânticas diferentes.

## Reprodução

```powershell
python analysis/home_advantage.py
```

Saídas tabulares: `analysis/home_advantage/by_decade.csv` e `analysis/home_advantage/by_season.csv`.
""", encoding="utf-8")


def self_check() -> None:
    assert abs(hedges_g(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))) < 1e-12
    sample = pd.DataFrame({"home_goals": [1, 0, 2], "away_goals": [0, 0, 3], "date_day": pd.to_datetime(["2020-01-01"] * 3)})
    prepared = prepare(sample)
    assert prepared.home_points.tolist() == [3, 1, 0]
    assert prepared.home_advantage_points.tolist() == [3, 0, -3]


def main() -> None:
    self_check()
    frame = prepare(load_matches())
    seasons = season_summary(frame)
    decades = decade_summary(frame, seasons)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    seasons.to_csv(OUTPUT / "by_season.csv", index=False)
    decades.to_csv(OUTPUT / "by_decade.csv", index=False)
    write_report(frame, seasons, decades)
    print(f"Partidas={len(frame):,} temporadas={len(seasons):,} relatório={REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
