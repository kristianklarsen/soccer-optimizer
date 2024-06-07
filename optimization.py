import mip
import matplotlib as mpl
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
from mplsoccer import VerticalPitch, Sbopen, FontManager, inset_image
from enum import Enum
from thefuzz import fuzz

from data import HoldetDk, ApiFootball, EVENTS


class ProbabilitySource(Enum):
    """Indicates the source of the probability of a given event."""
    PREDICTIONS = 0
    ODDS = 1


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
            if not all(len(fixture) > 0 for i, fixture in self.predictions.items()):
                raise Exception("One or more predictions could not be fetched from the api-football api.")
            prob_sum = sum(
                float(fixture[0]['predictions']['percent']['home'].replace('%', '')) / 100
                if fixture[0]['teams']['home']['id'] == self.team_id_map[player["team_id"]]
                else float(fixture[0]['predictions']['percent']['away'].replace('%', '')) / 100
                if fixture[0]['teams']['away']['id'] == self.team_id_map[player["team_id"]]
                else 0
                for i, fixture in self.predictions.items() if len(fixture) > 0
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


class Optimization:
    """Optimization class."""

    def __init__(self, optimization_input: OptimizationInput):
        self.model = mip.Model(solver_name=mip.CBC)
        self.input = optimization_input

    # TODO: consider adding existing team to enable adding switching cost

    def build_model(self):

        # Add selection variable for each player, and objective coefficient expected score
        x = [
            self.model.add_var(
                name=str(player["player_id"]),
                var_type=mip.BINARY
            ) for player in self.input.players
        ]

        # Add formation constraints
        goalkeepers = [
            x[i] if player["position_name"] == "Mål" else 0 for i, player in enumerate(self.input.players)
        ]
        defenders = [
            x[i] if player["position_name"] == "Forsvar" else 0 for i, player in enumerate(self.input.players)
        ]
        midfielders = [
            x[i] if player["position_name"] == "Midtbane" else 0 for i, player in enumerate(self.input.players)
        ]
        attackers = [
            x[i] if player["position_name"] == "Angreb" else 0 for i, player in enumerate(self.input.players)
        ]
        self.model.add_constr(
            name="Exactly 11 players",
            lin_expr=sum(x) == 11
        )
        self.model.add_constr(
            name="Formation exactly 1 goalkeeper",
            lin_expr=mip.xsum(goalkeepers) == 1
        )
        self.model.add_constr(
            name="Formation max 5 defenders",
            lin_expr=mip.xsum(defenders) <= 5
        )
        self.model.add_constr(
            name="Formation min 3 defenders",
            lin_expr=mip.xsum(defenders) >= 3
        )
        self.model.add_constr(
            name="Formation max 5 midfielders",
            lin_expr=mip.xsum(midfielders) <= 5
        )
        self.model.add_constr(
            name="Formation min 3 midfielders",
            lin_expr=mip.xsum(midfielders) >= 3
        )
        self.model.add_constr(
            name="Formation max 3 attackers",
            lin_expr=mip.xsum(attackers) <= 3
        )
        self.model.add_constr(
            name="Formation min 1 attacker",
            lin_expr=mip.xsum(attackers) >= 1
        )

        # Add team constraints
        teams = list(set([player["team_name"] for player in self.input.players]))
        players_by_team = [
            [
                x[i] if player["team_name"] == team else 0 for i, player in enumerate(self.input.players)
            ] for team in teams
        ]
        for team in players_by_team:
            self.model.add_constr(
                name="Max 4 players from same team",
                lin_expr=mip.xsum(team) <= 4
            )

        # Add budget constraint
        budget = 50000000
        min_spend_portion = 0.95
        team_value = mip.xsum(x[i] * player['current_value'] for i, player in enumerate(self.input.players))
        self.model.add_constr(
            name="Budget constraint",
            lin_expr=team_value <= budget
        )
        self.model.add_constr(
            name="Minimum spend constraint",
            lin_expr=team_value >= budget * min_spend_portion
        )

        # Add objective
        self.model.objective = mip.maximize(
            mip.xsum(
                x[i] * player["expected_score"] for i, player in enumerate(self.input.players)
            )
        )

    def run(self):
        # optimize and return results
        self.model.verbose = False
        self.model.optimize(max_seconds=30)

    def get_result(self) -> dict:
        """Returns optimum, i.e. selected players that optimizes expected score."""
        selected_player_ids = [int(var.name) for var in self.model.vars._VarList__vars if var.x == 1]
        players = [
                {
                    "person_fullname": next(
                        (
                            player["person_fullname"]
                            for player in self.input.players if player['player_id'] == player_id
                        ),
                        None
                    ),
                    "position_name_en": next(
                        (
                            player["position_name_en"]
                            for player in self.input.players if player['player_id'] == player_id
                        ),
                        None
                    ),
                    "team_name": next(
                        (
                            player["team_name"]
                            for player in self.input.players if player['player_id'] == player_id
                        ),
                        None
                    ),
                }
                for player_id in selected_player_ids
            ]
        formation = (
            f"{len([p for p in players if p['position_name_en'] == 'Defense'])}"
            f"{len([p for p in players if p['position_name_en'] == 'Midfielder'])}"
            f"{len([p for p in players if p['position_name_en'] == 'Striker'])}"
        )
        players_total_value = sum(
            player['current_value'] for player in self.input.players if player['player_id'] in selected_player_ids
        )
        return {
            "optimal_team": players,
            "formation": formation,
            "expected_score": self.model.objective_value,
            "players_total_value": players_total_value
        }


# class Visualization:
#     """Visualize output."""
#
#     def __init__(self, players: list[dict]):
#         self.players = players
#
#     def formation(self):
#         pitch = VerticalPitch(goal_type='box')
#         fig, ax = pitch.draw(figsize=(6, 8.72))
#         ax_text = pitch.formation(formation, positions=starting_xi.position_id, kind='text',
#                                   text=starting_xi.player_name.str.replace(' ', '\n'),
#                                   va='center', ha='center', fontsize=16, ax=ax)
#         # scatter markers
#         mpl.rcParams['hatch.linewidth'] = 3
#         mpl.rcParams['hatch.color'] = '#a50044'
#         ax_scatter = pitch.formation(formation, positions=starting_xi.position_id, kind='scatter',
#                                      c='#004d98', hatch='||', linewidth=3, s=500,
#                                      # you can also provide a single offset instead of a list
#                                      # for xoffset and yoffset
#                                      xoffset=-8,
#                                      ax=ax)

