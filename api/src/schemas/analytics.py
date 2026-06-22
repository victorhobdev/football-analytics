from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


AnalyticsMetricFilter = Literal[
    "matches", "goals", "avg_goals", "home_wins", "away_wins", "draws",
    "points", "goals_for", "goals_against", "goal_diff",
    "points_per_match", "win_rate", "ppg",
]

AnalyticsDimensionFilter = Literal["round", "team", "coach", "venue", "period"]

AnalyticsGrainFilter = Literal[
    "competition_season",
    "competition_season_round",
    "competition_season_team",
    "competition_season_team_round",
    "competition_season_coach",
]

AnalyticsOperationFilter = Literal["slice", "dice", "drill_down", "roll_up", "pivot", "drill_through"]

AnalyticsBreakdownFilter = Literal["venue", "round", "team", "none"]

AnalyticsPeriodType = Literal["round", "month"]

AnalyticsComparisonType = Literal[
    "team_vs_team", "season_vs_season", "home_vs_away", "period_vs_period",
]

AnalyticsSuperlativeCategory = Literal[
    "most_goals_match", "biggest_win", "best_attack", "best_defense",
    "best_goal_diff", "most_goals_round", "highest_avg_goals_round",
    "best_team_ppg", "coach_best_ppm", "coach_most_matches",
]


class CoverageInfo(BaseModel):
    status: str
    percentage: float | None = None
    sampleSize: int = 0
    expectedSize: int = 0
    label: str | None = None
    details: str | None = None
