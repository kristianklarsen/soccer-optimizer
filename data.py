import requests
import json
import pandas as pd
from typing import List, Dict

# Look at player team performance stats data at https://github.com/C-Roensholt/ScrapeDanishSuperligaData
#

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
    "Silkeborg IF": "Silkeborg"
}
"""Team name map from Holdet (key) to Odds data (value)."""

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
    4107: 2073
}
"""Team ID map from Holdet (key) to Odds data (value)."""

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


class HoldetData:
    """Data import class from Holdet.dk."""

    # For now defaults to select game "Super Manager" for edition "Fall 2023" with ID 665.
    def __init__(self, game_id: int = 665):
        self.game_id = game_id
        self.game_data = self.get_game_data()
        self.tournament_data = self.get_tournament_data()
        self.ruleset_data = self.get_ruleset_data()
        self.player_data = self.get_player_data()

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
                                     'position_id': player['position']['id'], }
        ruleset_data = self.ruleset_data
        positions = {}
        for position in ruleset_data['positions']:
            positions[position['id']] = {'position_id': position['id'],
                                         'position_name': position['name']}
        player_data = pd.DataFrame.from_dict(players, orient='index').merge(
            pd.DataFrame.from_dict(persons, orient='index'), on='person_id', how='left').merge(
            pd.DataFrame.from_dict(teams, orient='index'), on='team_id', how='left').merge(
            pd.DataFrame.from_dict(positions, orient='index'), on='position_id', how='left'
        )

        return player_data.to_dict('records')


class OddsData:
    """Data import class for odds. Default league is danish Superliga. Season is the current season."""

    def __init__(self, api_key: str, league_id=119, season=2023, events: dict = EVENTS, bookmaker: str = "Bet365"):
            self.api_key = api_key
            self.league_id = league_id
            self.season = season
            self.events = events
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

        if response.status_code == 200:
            return response.json()["response"]
        else:
            print("Failed to retrieve data. Status code:", response.status_code)
            return None

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

    def _curate_odds_data_match_winner(self, fixture: Dict):
        """Curate the odds data for a fixture for the event type match_winner."""

        fixture_data = next(filter(lambda x: x["fixture"]['id'] == fixture["fixture"]["id"], self.fixtures))
        fixture["home_team_id"] = fixture_data["teams"]["home"]["id"]
        fixture["away_team_id"] = fixture_data["teams"]["away"]["id"]
        # make home/away odds easily available
        odd_data = next(filter(lambda x: x["name"] == self.bookmaker, fixture["bookmakers"]))
        fixture["home_team_odd"] = float(next(
            filter(lambda x: x["value"] == "Home", odd_data["bets"][0]["values"])
        )["odd"])
        fixture["away_team_odd"] = float(next(
            filter(lambda x: x["value"] == "Away", odd_data["bets"][0]["values"])
        )["odd"])

    def get_odds(self, rounds_ahead: int = 1):
        """get odds for x next rounds for all events."""

        ##rounds = self._get_round_ids()
        odds = {}
        for event_key, event in self.events.items():
            odds[event_key] = self._get_odds_request(
                league=self.league_id, season=self.season, bet=event["bet_id"]
            )

            # Add additional relevant fields for each event type.
            if event_key == "match_winner":
                for fixture in odds[event_key]:
                    self._curate_odds_data_match_winner(fixture)

        return odds


class OptimizationInput:
    """Data class combining HoldetData and OddsData to get relevant input for optimization."""

    def __init__(self, holdet_data: HoldetData, odds_data: OddsData, team_id_map: dict = TEAM_ID_MAP):
        self.holdet_data = holdet_data
        self.odds_data = odds_data
        self.odds = {}
        self.team_id_map = team_id_map
        self.players = self._get_expected_player_scores()

    def _calc_expected_score_match_winner(self, player) -> float:
        """Calculate and return the expected score for a player for the event type match_winner."""

        return sum(
            [1 / odd["home_team_odd"] if odd["home_team_id"] == self.team_id_map[player["team_id"]] else
             1 / odd["away_team_odd"] if odd["away_team_id"] == self.team_id_map[player["team_id"]] else
             0
             for odd in self.odds["match_winner"]
             ]
        ) * next(
            filter(lambda x: x["name"] == "SoccerPlayerTeamWon",
                   self.holdet_data.ruleset_data["fantasyEventTypes"])
        )["value"]

    def _get_expected_player_scores(self):
        """Get list of players including expected score."""

        self.odds = self.odds_data.get_odds()
        player_scores = self.holdet_data.player_data
        for event_key, event in self.odds_data.events.items():
            if event_key == "match_winner":
                for player in player_scores:
                    player["expected_score"] = self._calc_expected_score_match_winner(player)

        return player_scores
