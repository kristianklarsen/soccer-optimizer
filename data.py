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

BET_ID_EVENT_TYPE_MAP = {
    300: 1,     # player team won   (using "match winner" bet. Select "Home" or "Away" odd based on player.)
    286: 92,    # goalkeeper goal   (using "anytime goal scorer" bet. Select event type based on player position.)
    281: 92,    # defense goal      (using "anytime goal scorer" bet. Select event type based on player position.)
    291: 92,    # midfielder goal   (using "anytime goal scorer" bet. Select event type based on player position.)
    305: 92,    # striker goal      (using "anytime goal scorer" bet. Select event type based on player position.)
}
"""Map from Holdet event type ID (key) to corresponding bet ID (value)."""


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

    def get_player_data(self) -> pd.DataFrame:
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

        return player_data


class OddsData:
    """Data import class for odds. Default league is danish Superliga. Season is the current season."""

    def __init__(self, api_key: str, league_id=119, season=2023):
            self.api_key = api_key
            self.base_url = "https://v3.football.api-sports.io"
            self.headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self.api_key
            }
            self.league_id = league_id
            self.season = season

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

    def get_odds(self, **params):
        """Get odds from fixtures, leagues or date."""

        url = f"{self.base_url}/odds"

        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 200:
            return response.json()["response"]
        else:
            print("Failed to retrieve data. Status code:", response.status_code)
            return None
