from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.src.main import app


class MarketTransfersApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("api.src.routers.market.db_client.fetch_all")
    def test_market_transfers_filters_by_type_and_returns_pagination(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "transfer_id": 1,
                "player_id": 10,
                "player_name": "Jogador A",
                "from_team_id": 100,
                "from_team_name": "Clube A",
                "to_team_id": 200,
                "to_team_name": "Clube B",
                "transfer_date": date(2025, 7, 1),
                "completed": True,
                "career_ended": False,
                "type_id": 219,
                "amount": "1000000",
                "_total_count": 3,
            }
        ]

        response = self.client.get(
            "/api/v1/market/transfers?typeId=219&page=2&pageSize=1&search=Jogador"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["items"][0]["typeId"], 219)
        self.assertEqual(payload["data"]["items"][0]["typeName"], "Transferência definitiva")
        self.assertEqual(payload["meta"]["pagination"]["page"], 2)
        self.assertEqual(payload["meta"]["pagination"]["pageSize"], 1)
        self.assertEqual(payload["meta"]["pagination"]["totalCount"], 3)
        self.assertTrue(payload["meta"]["pagination"]["hasNextPage"])
        self.assertTrue(payload["meta"]["pagination"]["hasPreviousPage"])

        query, params = fetch_all_mock.call_args.args
        self.assertIn("spt.type_id = %s", query)
        self.assertEqual(params.count(219), 2)

    @patch("api.src.routers.market.db_client.fetch_all")
    def test_market_transfers_returns_unknown_type_fallback(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "transfer_id": 2,
                "player_id": 20,
                "player_name": "Jogador B",
                "from_team_id": None,
                "from_team_name": None,
                "to_team_id": None,
                "to_team_name": None,
                "transfer_date": None,
                "completed": False,
                "career_ended": False,
                "type_id": 99999,
                "amount": None,
                "_total_count": 1,
            }
        ]

        response = self.client.get("/api/v1/market/transfers")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["items"][0]["typeName"], "Tipo desconhecido")

    @patch("api.src.routers.market.db_client.fetch_all")
    def test_market_transfers_sorts_and_filters_by_amount(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = [
            {
                "transfer_id": 3,
                "player_id": 30,
                "player_name": "Jogador C",
                "from_team_id": 300,
                "from_team_name": "Clube C",
                "to_team_id": 400,
                "to_team_name": "Clube D",
                "transfer_date": date(2025, 8, 1),
                "completed": True,
                "career_ended": False,
                "type_id": 219,
                "amount": "25000000",
                "amount_value": 25000000,
                "_total_count": 1,
            }
        ]

        response = self.client.get(
            "/api/v1/market/transfers?sortBy=amount&sortDirection=desc&hasAmount=true&minAmount=25000000&maxAmount=100000000"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["items"][0]["amountValue"], 25000000)
        self.assertEqual(payload["data"]["items"][0]["currency"], "EUR")

        query, params = fetch_all_mock.call_args.args
        self.assertIn("order by amount_value desc", query)
        self.assertEqual(params.count(True), 1)
        self.assertEqual(params.count(25000000.0), 2)
        self.assertEqual(params.count(100000000.0), 2)

    @patch("api.src.routers.market.db_client.fetch_all")
    def test_market_transfers_filters_club_direction(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = []

        response = self.client.get(
            "/api/v1/market/transfers?clubSearch=Barcelona&teamDirection=arrivals"
        )

        self.assertEqual(response.status_code, 200)
        query, params = fetch_all_mock.call_args.args
        self.assertIn("%s::text in ('all', 'arrivals')", query)
        self.assertIn("%Barcelona%", params)
        self.assertIn("arrivals", params)

    @patch("api.src.routers.market.db_client.fetch_all")
    def test_market_transfers_short_circuits_when_scope_has_no_teams(self, fetch_all_mock) -> None:
        fetch_all_mock.return_value = []

        response = self.client.get("/api/v1/market/transfers?competitionId=71&seasonId=23628")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["items"], [])
        self.assertEqual(payload["meta"]["pagination"]["totalCount"], 0)
        self.assertEqual(fetch_all_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
