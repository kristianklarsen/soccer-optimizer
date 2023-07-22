import requests
import json
import pandas as pd
import http.client
from typing import List

# Look at player team performance stats data at https://github.com/C-Roensholt/ScrapeDanishSuperligaData
#


class HoldetData:
    """Data import class from Holdet.dk."""

    # For now defaults to select game "Super Manager" for edition "Spring 2023".
    def __init__(self, game_id: int = 650):
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
    """Data import class for odds"""

    def __init__(self, api_key: str, league_id: int = 310):
            self.api_key = api_key
            self.request_headers = {
            'x-rapidapi-host': "v3.football.api-sports.io",
            'x-rapidapi-key': self.api_key
            }
            self.conn = http.client.HTTPSConnection("v3.football.api-sports.io")
            self.league_id = league_id

    def get_leagues(self) -> List:
        """Get the list of available leagues and cups."""

        self.conn.request("GET", "/leagues", headers=self.request_headers)

        res = self.conn.getresponse()
        data = res.read()
        results = json.loads(data)["response"]

        return results

    def get_fixtures(self):
        """Get data for multiple fixtures at once."""

        self.conn.request("GET", "/fixtures", headers=self.request_headers)

        res = self.conn.getresponse()
        data = res.read()
        results = json.loads(data)["response"]

        return results

    def get_bets(self) -> List:
        """Get all available bets for pre-match odds."""

        self.conn.request("GET", "/odds/bets", headers=self.request_headers)

        res = self.conn.getresponse()
        data = res.read()
        results = json.loads(data)["response"]

        return results

    def get_odds_fixtures_mapping(self):
        """Get the list of available fixtures id for the endpoint odds."""

        self.conn.request("GET", "/odds/mapping", headers=self.request_headers)

        res = self.conn.getresponse()
        data = res.read()
        results = json.loads(data)["response"]

        return results

    def get_odds(self):

