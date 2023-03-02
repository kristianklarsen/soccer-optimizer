import requests
import json


class HoldetData():
    """Data import class from Holdet.dk."""

    def __init__(self, game_id: int):
        self.game_id = game_id
        self.game_data = self.get_game_data(self.game_id)
        self.tournament_data = self.get_tournament_data(self.game_data['tournament']['id'])

    @staticmethod
    def get_game_data(game_id) -> dict:
        game_data = requests.get(
            f"https://api.holdet.dk/catalog/games/{game_id}?v=3&appid=holdet&culture=da-DK")
        game_data_json = json.loads(game_data.text)
        return game_data_json

    @staticmethod
    def get_tournament_data(tournament_id: int) -> dict:
        tournament_data = requests.get(
            f"https://api.holdet.dk/tournaments/{tournament_id}?appid=holdet&culture=da-DK")
        tournament_data_json = json.loads(tournament_data.text)
        return tournament_data_json

    # def get_player_data(self):
    #     """
    #     Get player data.
    #     Returns:
    #
    #     """
    #
    #     tournament_data = self.get_tournament_data()
    #     teams = {}
    #     for team in tournament_data['teams']:
    #         teams[team['id']] = {'team_id': team['id'],
    #                              'team_name': team['name']}
    #     persons = {}
    #     for person in tournament_data['persons']:
    #         persons[person['id']] = {'person_id': person['id'],
    #                                  'person_fullname': "".join(
    #                                      [person['firstname'], " " if person['lastname'] != "" else "",
    #                                       person['lastname']]),
    #                                  'person_shortname': "".join(
    #                                      [person['firstname'][0] if person['lastname'] != "" else person['firstname'],
    #                                       ". " if person['lastname'] != "" else "", person['lastname']])}
    #     players = {}
    #     for player in tournament_data['players']:
    #         players[player['id']] = {'player_id': player['id'],
    #                                  'person_id': player['person']['id'],
    #                                  'team_id': player['team']['id'],
    #                                  'position_id': player['position']['id'], }
    #
    #     ruleset_response = requests.get(
    #         f"https://api.holdet.dk/rulesets/{str(game_dict['ruleset_id'])}?appid=holdet&culture=da-DK")
    #     ruleset = json.loads(ruleset_response.text)
    #
    #     positions = {}
    #     for position in ruleset['positions']:
    #         positions[position['id']] = {'position_id': position['id'],
    #                                      'position_name': position['name']}
    #
    #     positions_df = pd.DataFrame.from_dict(positions, orient='index')
    #
    #     player_dimensions = players_df.merge(persons_df, on='person_id', how='left')
    #     player_dimensions = player_dimensions.merge(teams_df, on='team_id', how='left')
    #     player_dimensions = player_dimensions.merge(positions_df, on='position_id', how='left')
    #
    #     player_dimensions = player_dimensions[
    #         ['player_id', 'person_fullname', 'person_shortname', 'team_name', 'position_name']]
    #
    #     player_dimensions.rename(columns={'player_id': 'player_id',
    #                                       'person_fullname': 'name',
    #                                       'person_shortname': 'short_name',
    #                                       'team_name': 'team',
    #                                       'position_name': 'position'}, inplace=True)
    #
    #     return player_dimensions
