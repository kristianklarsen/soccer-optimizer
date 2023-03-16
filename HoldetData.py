import requests
import json
import pandas as pd


class HoldetData():
    """Data import class from Holdet.dk."""

    # For now defaults to select game "Super Manager" for edition "Spring 2023".
    def __init__(self, game_id: int = 650):
        self.game_id = game_id
        self.game_data = self.get_game_data(self.game_id)
        self.tournament_data = self.get_tournament_data(self.game_data['tournament']['id'])
        self.ruleset_data = self.get_ruleset_data(self.game_data['ruleset']['id'])
        self.player_data = self.get_player_data(self.tournament_data, self.ruleset_data)

    @staticmethod
    def get_game_data(game_id) -> dict:
        game_data = requests.get(
            f"https://api.holdet.dk/catalog/games/{game_id}?v=3&appid=holdet&culture=da-DK")
        game_data_dict = json.loads(game_data.text)
        return game_data_dict

    @staticmethod
    def get_tournament_data(tournament_id: int) -> dict:
        tournament_data = requests.get(
            f"https://api.holdet.dk/tournaments/{tournament_id}?appid=holdet&culture=da-DK")
        tournament_data_dict = json.loads(tournament_data.text)
        return tournament_data_dict

    @staticmethod
    def get_ruleset_data(ruleset_id: int) -> dict:
        ruleset_response = requests.get(
            f"https://api.holdet.dk/rulesets/{ruleset_id}?appid=holdet&culture=da-DK")
        ruleset_dict = json.loads(ruleset_response.text)
        return ruleset_dict

    @staticmethod
    def get_player_data(tournament_data: dict, ruleset_data: dict) -> pd.DataFrame:
        """
        Get player data.
        Returns:

        """

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
