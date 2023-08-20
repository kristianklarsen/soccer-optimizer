import requests
import json
import pandas as pd

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

EVENTS = {
    "match_winner": {       # player team won   (using "match winner" bet. Select "Home" or "Away" odd based on player.)
        "holdet_event_id": 300,
        "bet_id": 1,
        "key_item": "team_name"
    },
    "anytime_goal_goalkeeper": {       # goalkeeper goal   (using "anytime goal scorer" bet. Select event type based on player position.)
        "holdet_event_id": 286,
        "bet_id": 92,
        "key_item": "player_id",
        "static_filter_item": "position_name",
        "static_filter_value": "goal_keeper"
    },
    "anytime_goal_defense": {       # defense goal      (using "anytime goal scorer" bet. Select event type based on player position.)
        "holdet_event_id": 281,
        "bet_id": 92,
        "key_item": "player_id",
        "static_filter_item": "position_name",
        "static_filter_value": "defender"
    },
    "anytime_goal_midfielder": {       # midfielder goal   (using "anytime goal scorer" bet. Select event type based on player position.)
        "holdet_event_id": 291,
        "bet_id": 92,
        "key_item": "player_id",
        "static_filter_item": "position_name",
        "static_filter_value": "midfielder"
    },
    "anytime_goal_striker": {       # striker goal      (using "anytime goal scorer" bet. Select event type based on player position.)
        "holdet_event_id": 305,
        "bet_id": 92,
        "key_item": "player_id",
        "static_filter_item": "position_name",
        "static_filter_value": "striker"
    },
}
"""List of Holdet events for which points can be scored in the Holdet game. Contains mapping ids for corresponding bet,
as well as key_item, and potentially static filters, used to link the bet/odds with relevant players."""


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

    def get_player_data(self) -> dict:
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

        return player_data.to_dict()


class OddsData:
    """Data import class for odds. Default league is danish Superliga. Season is the current season."""

    def __init__(self, api_key: str, league_id=119, season=2023, events: dict = EVENTS):
            self.api_key = api_key
            self.league_id = league_id
            self.season = season
            self.events = events
            self.base_url = "https://v3.football.api-sports.io"
            self.headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self.api_key
            }

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

    def get_fixtures(self):
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

    def get_odds(self, rounds_ahead: int = 1):
        """get odds for x next rounds for all events."""

        ##rounds = self._get_round_ids()
        odds = {}
        for event_key, event in self.events.items():
            odds[event_key] = self._get_odds_request(
                league=self.league_id, season=self.season, bet=event["bet_id"]
            )

        return odds


class OptimizationInput:
    """Data class combining HoldetData and OddsData to get relevant input for optimization."""

    def __init__(self, holdet_data: HoldetData, odds_data: OddsData):
        self.holdet_data = holdet_data
        self.odds_data = odds_data
        self.players = holdet_data.player_data

    def _get_expected_scores(self):
        """Get list of players including expected score."""

        for event_key, event in self.odds_data.events.items():
            players_enriched = self.players.


