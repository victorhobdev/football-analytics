from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class CoachesRouteContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.coaches.db_client.fetch_all")
    def test_coach_list_neutralizes_public_fallbacks_and_placeholder_photo(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "coach_id": 10,
                "coach_name": "Unknown Coach #10",
                "photo_url": "https://cdn.example.com/placeholder.png",
                "has_real_photo": True,
                "is_placeholder_image": True,
                "tenure_count": 1,
                "active_tenures": 1,
                "matches": 4,
                "wins": 2,
                "draws": 1,
                "losses": 1,
                "points": 7,
                "goals_for": 6,
                "goals_against": 4,
                "adjusted_ppm": 1.7,
                "points_per_match": 1.75,
                "last_match_date": "2025-01-10",
                "team_id": 700,
                "team_name": "Unknown Team #700",
                "active": True,
                "temporary": False,
                "start_date": "2025-01-01",
                "end_date": None,
                "league_id": None,
                "league_name": None,
                "season": 2025,
                "_total_count": 1,
            }
        ]

        response = self.client.get("/api/v1/coaches")

        self.assertEqual(response.status_code, 200)
        item = response.json()["data"]["items"][0]
        self.assertEqual(item["coachName"], "Nome indisponível")
        self.assertEqual(item["teamName"], "Time indisponível")
        self.assertIsNone(item["photoUrl"])
        self.assertFalse(item["hasRealPhoto"])
        self.assertEqual(item["mediaStatus"], "provider_placeholder")
        self.assertEqual(item["dataStatus"], "partial")

    @patch("api.src.routers.coaches.db_client.fetch_all")
    def test_coach_profile_neutralizes_current_team_and_tenure_fallbacks(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "coach_id": 10,
                "coach_name": "Técnico #10",
                "photo_url": None,
                "has_real_photo": False,
                "is_placeholder_image": False,
                "tenure_count": 1,
                "active_tenures": 0,
                "teams_count": 1,
                "total_matches": 4,
                "total_wins": 2,
                "total_draws": 1,
                "total_losses": 1,
                "total_points": 7,
                "total_goals_for": 6,
                "total_goals_against": 4,
                "total_adjusted_ppm": 1.7,
                "total_points_per_match": 1.75,
                "total_last_match_date": "2025-01-10",
                "current_team_id": 700,
                "current_team_name": "Team #700",
                "current_active": False,
                "current_temporary": False,
                "current_start_date": "2025-01-01",
                "current_end_date": "2025-01-10",
                "coach_tenure_id": 123,
                "team_id": 700,
                "team_name": "Unknown Team #700",
                "active": False,
                "temporary": False,
                "start_date": "2025-01-01",
                "end_date": "2025-01-10",
                "matches": 4,
                "wins": 2,
                "draws": 1,
                "losses": 1,
                "points": 7,
                "goals_for": 6,
                "goals_against": 4,
                "points_per_match": 1.75,
                "last_match_date": "2025-01-10",
                "league_id": None,
                "league_name": None,
                "season": 2025,
            }
        ]

        response = self.client.get("/api/v1/coaches/10")

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["coach"]["coachName"], "Nome indisponível")
        self.assertEqual(payload["coach"]["teamName"], "Time indisponível")
        self.assertEqual(payload["coach"]["mediaStatus"], "editorial_fallback")
        self.assertEqual(payload["coach"]["dataStatus"], "partial")
        self.assertEqual(payload["tenures"][0]["teamName"], "Time indisponível")
        self.assertEqual(payload["tenures"][0]["dataStatus"], "partial")


if __name__ == "__main__":
    unittest.main()
