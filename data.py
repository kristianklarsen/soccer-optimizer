import requests
import json
import logging
import pandas as pd
import datetime as dt
from typing import List, Dict

# Look at player team performance stats data at https://github.com/C-Roensholt/ScrapeDanishSuperligaData
# TODO: make imports of datasets for "predictions".
#  make ready for importing additional dataset of matches during championship.
#  (adjust stats using these by some fraction)
#  maybe use API instead? https://footystats.org/api/
#
# TODO: wrap up in Flask app.
#  try deploy Flask app from localhost using e.g. pinggy.io
#  later deploy via https://cloud.google.com/run#pricing   (cheapest)


TEAM_NAME_MAP = {
    "Vejle Boldklub": "Vejle",
    "FC Midtjylland": "FC Midtjylland",
    "FC Nordsjælland": "FC Nordsjaelland",
    "FC København": "FC Copenhagen",
    "Randers FC": "Randers FC",
    "OB": "Odense",
    "AGF": "Aarhus",
    "Brøndby IF": "Brondby",
    "Lyngby BK": "Lyngby",
    "Viborg FF": "Viborg",
    "Hvidovre IF": "Hvidovre",
    "Silkeborg IF": "Silkeborg",

}
"""Team name map from Holdet (key) to ApiFootball data (value)."""

TEAM_ID_MAP = {
    3977: 395,
    3952: 397,
    3953: 398,
    3951: 400,
    3956: 401,
    3955: 405,
    3948: 406,
    3949: 407,
    3954: 625,
    3957: 2070,
    4245: 2072,
    4107: 2073,
    3966: 25,
    4921: 1108,
    4740: 769,
    3959: 15,
    3972: 9,
    3964: 3,
    3971: 768,
    4739: 778,
    4304: 1091,
    4290: 21,
    4302: 14,
    4291: 10,
    3970: 1118,
    3963: 775,
    3969: 2,
    4648: 1,
    4303: 773,
    3968: 774,
    3962: 777,
    3961: 27,
    3960: 770,
    5128: 1104,
    3967: 24,
    4511: 772
}
"""Team ID map from Holdet (key) to ApiFootball data (value)."""

EVENTS = {
    "match_winner": {    # player team won   (using "match winner" bet. Select "Home" or "Away" odd based on player.)
        "holdet_event_id": 300,
        "bet_id": 1,
    },
    "anytime_goal_goalkeeper": {
        "holdet_event_id": 286,
        "bet_id": 92,
    },
    "anytime_goal_defense": {
        "holdet_event_id": 281,
        "bet_id": 92,
    },
    "anytime_goal_midfielder": {
        "holdet_event_id": 291,
        "bet_id": 92,
    },
    "anytime_goal_striker": {
        "holdet_event_id": 305,
        "bet_id": 92,
    },
}
"""List of Holdet events for which points can be scored in the Holdet game and for which a relevant bet exists. Contains
mapping IDs for corresponding bet.
"""


class HoldetDk:
    """Data import class from https://www.holdet.dk/da."""

    # Default game is EURO 2024.
    def __init__(self, game_id: int = 686):
        self.game_id = game_id
        self.game_data = self.get_game_data()
        self.tournament_data = self.get_tournament_data()
        self.ruleset_data = self.get_ruleset_data()
        self.player_data = self.get_player_data()
        self.current_round_start_end_time = self.get_current_round_start_end_datetime()

    def get_game_data(self) -> dict:
        game_data = requests.get(
            f"https://api.holdet.dk/catalog/games/{self.game_id}?v=3&appid=holdet&culture=da-DK")
        game_data_dict = json.loads(game_data.text)
        return game_data_dict

    def get_tournament_data(self) -> dict:
        tournament_data = requests.get(
            f"https://api.holdet.dk/tournaments/{self.game_data['tournament']['id']}?appid=holdet&culture=da-DK")
        tournament_data_dict = json.loads(tournament_data.text)
        return tournament_data_dict

    def get_ruleset_data(self) -> dict:
        ruleset_response = requests.get(
            f"https://api.holdet.dk/rulesets/{self.game_data['ruleset']['id']}?appid=holdet&culture=da-DK")
        ruleset_dict = json.loads(ruleset_response.text)
        return ruleset_dict

    def get_player_data(self) -> List[dict]:
        tournament_data = self.tournament_data
        teams = {}
        for team in tournament_data['teams']:
            teams[team['id']] = {'team_id': team['id'],
                                 'team_name': team['name']}
        persons = {}
        for person in tournament_data['persons']:
            persons[person['id']] = {'person_id': person['id'],
                                     'person_fullname': "".join(
                                         [person['firstname'], " " if person['lastname'] != "" else "",
                                          person['lastname']]),
                                     'person_shortname': "".join(
                                         [person['firstname'][0] if person['lastname'] != "" else person['firstname'],
                                          ". " if person['lastname'] != "" else "", person['lastname']])}
        players = {}
        for player in tournament_data['players']:
            players[player['id']] = {'player_id': player['id'],
                                     'person_id': player['person']['id'],
                                     'team_id': player['team']['id'],
                                     'position_id': player['position']['id']}
        ruleset_data = self.ruleset_data
        positions = {}
        for position in ruleset_data['positions']:
            positions[position['id']] = {'position_id': position['id'],
                                         'position_name': position['name'],
                                         'position_name_en': 'Goalkeeper' if position['id'] == 6 else
                                         'Defense' if position['id'] == 7 else
                                         'Midfielder' if position['id'] == 8 else
                                         'Striker' if position['id'] == 9 else
                                         None
                                        }
        round_stats = self.get_current_round_stats()
        player_stats = {}
        for player in round_stats:
            player_stats[player['player']['id']] = {
                'player_id': player['player']['id'],
                'current_value': player['values']['value'],
                'growth_since_last_round': player['values']['growth'],
                'total_growth': player['values']['totalGrowth'],
                'popularity': player['values']['popularity']
            }
        player_data = pd.DataFrame.from_dict(players, orient='index').merge(
            pd.DataFrame.from_dict(persons, orient='index'), on='person_id', how='left').merge(
            pd.DataFrame.from_dict(teams, orient='index'), on='team_id', how='left').merge(
            pd.DataFrame.from_dict(positions, orient='index'), on='position_id', how='left').merge(
            pd.DataFrame.from_dict(player_stats, orient='index'), on='player_id', how='left'
        )
        return player_data.to_dict('records')

    def get_event_points(self, event_id: int) -> float:
        """Get the amount of points awarded for a given event ID."""

        return [event["value"] for event in self.ruleset_data["fantasyEventTypes"] if event["id"] == event_id][0]

    def get_current_round(self) -> int:
        """Return current round number (switches when round is closed for trading)."""
        current_time = dt.datetime.now(dt.timezone.utc)
        rnd_number = next(
            (
                i+1 for i, rnd in enumerate(self.game_data['rounds'])
                if current_time < dt.datetime.strptime(rnd['close'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
            ),
            None
        )
        if rnd_number is None:
            raise Exception("The selected game has ended.")
        else:
            return rnd_number

    def get_current_round_stats(self) -> dict:
        rnd_no = self.get_current_round()
        round_stats = requests.get(
            f"https://fs-api.swush.com/games/{self.game_id}/rounds/{rnd_no}/statistics?appid=holdet&culture=da")
        game_data_dict = json.loads(round_stats.text)
        return game_data_dict

    def get_current_round_start_end_datetime(self) -> (dt.datetime, dt.datetime):
        """Get the start and end datetime of the currently active round (switches when round is closed for trading)."""
        rnd_idx = self.get_current_round()-1
        rnd = self.game_data['rounds'][rnd_idx]
        return (
            dt.datetime.strptime(rnd['start'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc),
            dt.datetime.strptime(rnd['end'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
        )


class ApiFootball:
    """Data import class for odds and predictions from https://www.api-football.com/. Default league and season is
    danish Superliga and current season."""

    # TODO: auto find current season.

    def __init__(self, api_key: str, league_id: int = 4, season: int = 2024, bookmaker: str = "Bet365"):
            self.api_key = api_key
            self.league_id = league_id
            self.season = season
            self.bookmaker = bookmaker
            self.base_url = "https://v3.football.api-sports.io"
            self.headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self.api_key
            }
            self.fixtures = self._get_fixtures()

    def get_leagues(self):
        """Get the list of available leagues and cups."""

        url = f"{self.base_url}/leagues"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()["response"]
        else:
            print("Failed to retrieve data. Status code:", response.status_code)
            return None

    def get_teams(self):
        """Get teams data."""

        url = f"{self.base_url}/teams"
        response = requests.get(url, headers=self.headers, params={"league": self.league_id, "season": self.season})

        if response.status_code == 200:
            return response.json()["response"]
        else:
            print("Failed to retrieve data. Status code:", response.status_code)
            return None

    def _get_fixtures(self):
        """Get fixtures data for the season."""

        url = f"{self.base_url}/fixtures"
        response = requests.get(url, headers=self.headers, params={"league": self.league_id, "season": self.season})

        if response.status_code != 200:
            raise Exception(f"Failed to retrieve data from api-football. Status code: {response.status_code}")
        errors = response.json()["errors"] if len(response.json()["errors"]) > 0 else None
        if errors:
            raise Exception(f"The api-football api responded, but the following errors were raised: "
                            f"{print(errors)}")
        return response.json()["response"]

    def get_injuries(self):
        """Get injuries data for the season."""

        url = f"{self.base_url}/injuries"
        response = requests.get(url, headers=self.headers, params={"league": self.league_id, "season": self.season})

        if response.status_code != 200:
            raise Exception(f"Failed to retrieve data from api-football. Status code: {response.status_code}")
        errors = response.json()["errors"] if len(response.json()["errors"]) > 0 else None
        if errors:
            raise Exception(f"The api-football api responded, but the following errors were raised: "
                            f"{print(errors)}")
        return response.json()["response"]

    def get_bets(self):
        """Get all available bets for pre-match odds."""

        url = f"{self.base_url}/odds/bets"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()["response"]
        else:
            print("Failed to retrieve data. Status code:", response.status_code)
            return None

    def get_odds_fixtures_mapping(self):
        """Get the list of available fixtures id for the endpoint odds."""

        url = f"{self.base_url}/odds/mapping"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()["response"]
        else:
            print("Failed to retrieve data. Status code:", response.status_code)
            return None

    def _get_odds_request(self, **params):
        """Get odds from fixtures, leagues or date."""

        url = f"{self.base_url}/odds"

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            return response.json()["response"]
        else:
            print("Failed to retrieve data. Status code:", response.status_code)
            return None

    def get_odds(
            self,
            bet_ids: List[int],
            earliest_fixture_time_utc: dt.datetime = dt.datetime.now(dt.timezone.utc),
            latest_fixture_time_utc: dt.datetime = None
    ) -> Dict[int, List[Dict]]:
        """Get fixture odds for a list of bet IDs in the given time frame."""

        odds = {}
        for bet_id in bet_ids:
            odds[bet_id] = self._get_odds_request(
                league=self.league_id, season=self.season, bet=bet_id
            )
            # If there are any fixtures, apply date filter
            if len(odds[bet_id]) > 0:
                odds[bet_id] = [
                    fixture for fixture in odds[bet_id]
                    if (
                            earliest_fixture_time_utc <=
                            dt.datetime.fromisoformat(fixture['fixture']['date']) <=
                            latest_fixture_time_utc
                            if latest_fixture_time_utc
                            else earliest_fixture_time_utc <= dt.datetime.fromisoformat(fixture['fixture']['date'])
                    )
                ]
                if len(odds[bet_id]) == 0:
                    logging.warning(f'No odds founds for bookmaker {self.bookmaker} for bet ID: {bet_id}.')

        return odds

    def get_fixture_prediction_request(self, fixture_id):
        """Get predictions for a fixture."""

        url = f"{self.base_url}/predictions?fixture={fixture_id}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json()["response"]
        else:
            print("Failed to retrieve data. Status code:", response.status_code)
            return None

    def get_fixture_predictions(
            self,
            earliest_fixture_time_utc: dt.datetime = dt.datetime.now(dt.timezone.utc),
            latest_fixture_time_utc: dt.datetime = None
    ) -> Dict:
        """Get predictions for fixtures in a given period."""

        fixtures_in_period = [
            f['fixture']['id'] for f in self.fixtures
            if (
                earliest_fixture_time_utc <=
                dt.datetime.fromisoformat(f['fixture']['date']) <=
                latest_fixture_time_utc
                if latest_fixture_time_utc
                else earliest_fixture_time_utc <= dt.datetime.fromisoformat(f['fixture']['date'])
            )
        ]
        return {
            f: self.get_fixture_prediction_request(f) for f in fixtures_in_period
        }
