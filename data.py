import requests
import json
import logging
import pandas as pd
import datetime as dt
from typing import List, Dict
from thefuzz import fuzz
from enum import Enum

# Look at player team performance stats data at https://github.com/C-Roensholt/ScrapeDanishSuperligaData
# TODO: make imports of datasets for "predictions".
#  make ready for importing additional dataset of matches during championship.
#  (adjust stats using these by some fraction)
#  maybe use API instead? https://footystats.org/api/


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
    4107: 2073
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


class ProbabilitySource(Enum):
    """Indicates the source of the probability of a given event."""
    PREDICTIONS = 0
    ODDS = 1


class HoldetDk:
    """Data import class from https://www.holdet.dk/da."""

    # For now defaults to select game "Super Manager" for edition "Fall 2023" with ID 665.
    def __init__(self, game_id: int = 684):
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
        player_data = pd.DataFrame.from_dict(players, orient='index').merge(
            pd.DataFrame.from_dict(persons, orient='index'), on='person_id', how='left').merge(
            pd.DataFrame.from_dict(teams, orient='index'), on='team_id', how='left').merge(
            pd.DataFrame.from_dict(positions, orient='index'), on='position_id', how='left'
        )
        return player_data.to_dict('records')

    def get_event_points(self, event_id: int) -> float:
        """Get the amount of points awarded for a given event ID."""

        return [event["value"] for event in self.ruleset_data["fantasyEventTypes"] if event["id"] == event_id][0]

    def get_current_round_start_end_datetime(self) -> (dt.datetime, dt.datetime):
        """Get the start and end datetime of the current round."""

        current_time = dt.datetime.now(dt.timezone.utc)
        if current_time < dt.datetime.strptime(self.game_data['start'], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc):
            raise Exception("The selected game is not started.")
        elif current_time > dt.datetime.strptime(self.game_data['end'], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=dt.timezone.utc):
            raise Exception("The selected game has ended.")
        else:
            return [
                (
                    dt.datetime.strptime(rnd['start'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc),
                    dt.datetime.strptime(rnd['end'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
                ) for rnd in self.game_data['rounds'] if
                dt.datetime.strptime(rnd['start'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc) <
                current_time <
                dt.datetime.strptime(rnd['end'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
            ][0]


class ApiFootball:
    """Data import class for odds and predictions from https://www.api-football.com/. Default league and season is
    danish Superliga and current season."""

    # TODO: auto find current season.

    def __init__(self, api_key: str, league_id: int = 119, season: int = 2023, bookmaker: str = "Bet365"):
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


class OptimizationInput:
    """Combining HoldetDk and ApiFootball to get relevant input for optimization."""

    def __init__(self, holdet: HoldetDk, api_football: ApiFootball, team_id_map: dict, events: dict):
        self.holdet = holdet
        self.api_football = api_football
        self.team_id_map = team_id_map
        self.events = events
        self.odds = api_football.get_odds(
            bet_ids=list(set([event['bet_id'] for i, event in EVENTS.items()])),
            latest_fixture_time_utc=self.holdet.current_round_start_end_time[1]
        )
        self.predictions = self.api_football.get_fixture_predictions(
            earliest_fixture_time_utc=self.holdet.current_round_start_end_time[0],
            latest_fixture_time_utc=self.holdet.current_round_start_end_time[1]
        )
        self.players = self._get_expected_player_scores()

    # TODO: add method for clean sheet odd

    def _calc_expected_score_anytime_goal(self, player) -> float:
        """Calculate and return the expected score for a player for the event types anytime_goal_% (there is one for
        each player position)."""

        # TODO: consider adding some score (perhaps min) for each player in team not having an odd (not all players have
        #   odds)
        pos_name = player["position_name_en"].lower()
        return sum(
            1 / float(player_odd['odd']) for odds in [
                odd_data['bets'][0]['values'] for fixture in
                self.odds[self.events[f'anytime_goal_{pos_name}']['bet_id']] for odd_data in
                fixture['bookmakers'] if odd_data["name"] == self.api_football.bookmaker
            ] for player_odd in odds if fuzz.ratio(player_odd['value'], player['person_fullname']) > 80
        ) * self.holdet.get_event_points(self.events[f'anytime_goal_{pos_name}']['holdet_event_id'])

    def _calc_expected_score_match_winner(
            self, player, prob_source: ProbabilitySource = ProbabilitySource.PREDICTIONS
    ) -> float:
        """Calculate and return the expected score for a player for the event type match_winner."""

        if prob_source == ProbabilitySource.ODDS:
            match_winner_odds = self.odds[self.events['match_winner']['bet_id']]

            fixture_home_away_ids = {
                fixture["fixture"]['id']: (
                    fixture_data["teams"]["home"]["id"],
                    fixture_data["teams"]["away"]["id"]
                )
                for fixture in match_winner_odds
                for fixture_data in self.api_football.fixtures if fixture_data["fixture"]['id'] == fixture["fixture"]["id"]
            }
            prob_sum = sum(
                [
                    1 / [
                        [
                            float(odd["odd"]) for odd in odd_data["bets"][0]["values"] if odd["value"] == "Home"
                        ][0]
                        for odd_data in fixture["bookmakers"]
                        if odd_data["name"] == self.api_football.bookmaker
                    ][0]
                    if fixture_home_away_ids[fixture["fixture"]['id']][0] == self.team_id_map[player["team_id"]]
                    else
                    1 / [
                        [
                            float(odd["odd"]) for odd in odd_data["bets"][0]["values"] if odd["value"] == "Away"
                        ][0]
                        for odd_data in fixture["bookmakers"]
                        if odd_data["name"] == self.api_football.bookmaker
                    ][0]
                    if fixture_home_away_ids[fixture["fixture"]['id']][1] == self.team_id_map[player["team_id"]]
                    else
                    0
                    for fixture in match_winner_odds
                ]
            )

        elif prob_source == ProbabilitySource.PREDICTIONS:
            prob_sum = sum(
                float(fixture[0]['predictions']['percent']['home'].replace('%', '')) / 100
                if fixture[0]['teams']['home']['id'] == self.team_id_map[player["team_id"]]
                else float(fixture[0]['predictions']['percent']['away'].replace('%', '')) / 100
                if fixture[0]['teams']['away']['id'] == self.team_id_map[player["team_id"]]
                else 0
                for i, fixture in self.predictions.items()
            )
        else:
            raise Exception(f"ProbabilitySource {prob_source} not implemented here!")

        return prob_sum * self.holdet.get_event_points(self.events['match_winner']['holdet_event_id'])

    def _get_expected_player_scores(self):
        """Get list of players including expected score."""

        player_scores = self.holdet.player_data
        for event_key, event in self.events.items():
            if event_key == "match_winner":
                for player in player_scores:
                    player["expected_score"] = self._calc_expected_score_match_winner(player)
            #if 'anytime_goal_' in event_key:
            #    for player in player_scores:
            #        player["expected_score"] += self._calc_expected_score_anytime_goal(player)

        return player_scores
