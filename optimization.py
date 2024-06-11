import mip
import datetime as dt
import matplotlib as mpl
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
from mplsoccer import VerticalPitch, Sbopen, FontManager, inset_image
from enum import Enum
from thefuzz import fuzz
from typing import List

from data import HoldetDk, ApiFootball, EVENTS, Stats


class ProbabilitySource(Enum):
    """Indicates the source of the probability of a given event."""
    PREDICTIONS = 0
    ODDS = 1


class OptimizationInput:
    """Combining HoldetDk and ApiFootball to get relevant input for optimization."""

    def __init__(
            self,
            holdet: HoldetDk,
            api_football: ApiFootball,
            stats: Stats,
            team_id_map: dict,
            events: dict,
            existing_player_ids: List[int],
            bank_beholdning: float
    ):
        self.holdet = holdet
        self.api_football = api_football
        self.stats = stats
        self.team_id_map = team_id_map
        self.events = events
        self.existing_player_ids = existing_player_ids
        self.bank_beholdning = bank_beholdning
        self.odds = api_football.get_odds(
            bet_ids=list(set([event['bet_id'] for i, event in EVENTS.items()])),
            latest_fixture_time_utc=self.holdet.current_round_start_end_time[1]
        )
        self.predictions = self.api_football.get_fixture_predictions(
            earliest_fixture_time_utc=self.holdet.current_round_start_end_time[0],
            latest_fixture_time_utc=self.holdet.current_round_start_end_time[1]
        )
        self.players = self._get_expected_player_scores()

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

        player_prob_appear = self.stats.get_prob_appearance()
        player_scores = self.holdet.player_data
        for event_key, event in self.events.items():
            if event_key == "match_winner":
                for player in player_scores:
                    player_stats_name = self.name_lookup_holdet_to_stats(player['person_fullname'])
                    # Expected score from team win
                    win_match_exp_score = self._calc_expected_score_match_winner(player)
                    # Expected score from goals
                    pos_name = player["position_name_en"].lower()
                    goals_per_match_exp_score = self.stats.get_stat_players(
                        'goals_per_90_overall').get(player_stats_name, 0) * self.holdet.get_event_points(
                        self.events[f'anytime_goal_{pos_name}']['holdet_event_id']
                    )
                    # Expected score from assists
                    points_assist = self.holdet.get_event_points(278)
                    assists_per_match_exp_score = self.stats.get_stat_players(
                        'assists_per_90_overall').get(player_stats_name, 0) * points_assist
                    # TODO: add score from team goals
                    # Expected score from cards
                    points_red = self.holdet.get_event_points(303)
                    points_yellow = self.holdet.get_event_points(313)
                    points_card_avg = (points_red + points_yellow) * 0.5
                    cards_per_match_exp_score = self.stats.get_stat_players(
                        'cards_per_90_overall').get(player_stats_name, 0) * points_card_avg
                    # Expected score from clean sheets
                    points_defender = self.holdet.get_event_points(280)
                    points_gk = self.holdet.get_event_points(285)
                    appearances = self.stats.get_stat_players('appearances_overall').get(player_stats_name, 0)
                    clean_sheets = self.stats.get_stat_players('clean_sheets_overall').get(player_stats_name, 0)
                    p_clean_sheet = clean_sheets / appearances if appearances != 0 else 0
                    clean_sheet_exp_score = p_clean_sheet * (
                        points_defender if pos_name == 'defender' else
                        points_gk if pos_name == 'goalkeeper' else
                        0
                    )
                    # Combined expected score multiplied by probability of appearance
                    p_appear = player_prob_appear.get(player_stats_name, 0)
                    player["expected_score"] = p_appear * (
                            win_match_exp_score +
                            goals_per_match_exp_score +
                            clean_sheet_exp_score +
                            assists_per_match_exp_score +
                            cards_per_match_exp_score
                    )
            #if 'anytime_goal_' in event_key:
            #    for player in player_scores:
            #        player["expected_score"] += self._calc_expected_score_anytime_goal(player)

        return player_scores

    def get_current_round_injured_players(self):
        """Get list of player names who are injured for fixtures in the current round."""
        all_injuries = self.api_football.get_injuries()
        current_round_time_interval = self.holdet.current_round_start_end_time
        round_injuries = [
            injury for injury in all_injuries if
            current_round_time_interval[0] <
            dt.datetime.strptime(injury['fixture']['date'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc) <
            current_round_time_interval[1]
        ]
        return list(set(
            injury['player']['name'] for injury in round_injuries
        ))

    def get_budget(self):
        value_of_players = sum(player['current_value'] for player in self.players if player['player_id'] in self.existing_player_ids)
        cash = self.bank_beholdning
        return value_of_players + cash

    def name_lookup_stats_to_holdet_id(self, name: str, fuzz_match_ratio: float = 80) -> int | None:
        """Convert a player full name from stats files to HoldetDk identifier player_id. Based on fuzzy match."""

        return next(
            (
                player['player_id']
                for player in self.holdet.player_data
                if fuzz.ratio(name, player['person_fullname']) > fuzz_match_ratio
            ),
            None
        )

    # TODO: make a sort of "fuzzy map" to map all of the IDs
    def name_lookup_holdet_to_stats(self, holdet_player_id: str, fuzz_match_ratio: float = 80) -> str | None:
        """Convert a HoldetDk player name to player full name from stats files. Based on fuzzy match."""

        return next(
            (
                player_name
                for player_name in self.stats.get_stat_players('full_name').values()
                if fuzz.ratio(holdet_player_id, player_name) > fuzz_match_ratio
            ),
            None
        )


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

        # Add constraint to avoid injured or eliminated/non-active players
        injured_players = self.input.get_current_round_injured_players()
        injured_players_holdet_names = [
            player_holdet['person_fullname']
            for player_holdet in self.input.players
            for player_api in injured_players
            if fuzz.ratio(player_holdet['person_shortname'], player_api) > 80
        ]
        for i, player in enumerate(self.input.players):
            if player['is_eliminated'] or not player['is_active']:
                self.model.add_constr(
                    name=f"Avoid buying non-active or eliminated player {player['person_fullname']}.",
                    lin_expr=x[i] == 0
                )
            elif player['person_shortname'] in injured_players_holdet_names:
                self.model.add_constr(
                    name=f"Avoid buying injured player {player['person_fullname']}.",
                    lin_expr=x[i] == 0
                )
        # Exclude players below a given qualifier appearance level (to avoid solver choosing strategy of half team
        # with no appearance).
        min_prob_appear = 0.80
        player_prob_appear = self.input.stats.get_prob_appearance()
        for i, player in enumerate(self.input.players):
            player_stats_name = self.input.name_lookup_holdet_to_stats(player['person_fullname'])
            p_appear = player_prob_appear.get(player_stats_name, 0)
            if p_appear < min_prob_appear:
                self.model.add_constr(
                    name=f"Avoid buying player with low probability of appearance {player['person_fullname']}.",
                    lin_expr=x[i] == 0
                )

        # Add budget constraint
        budget = self.input.get_budget()
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

        # Define objective terms
        transfer_cost_rate = 0.01
        transfer_costs_shift_in = [
            -player['current_value'] * transfer_cost_rate   # Transfer costs to shift in a player
            if player['player_id'] not in self.input.existing_player_ids
            else 0
            for i, player in enumerate(self.input.players)
        ]
        transfer_costs_shift_out = [
            player['current_value'] * transfer_cost_rate    # Transfer cost lost if shifting out a player
            if player['player_id'] in self.input.existing_player_ids
            else 0
            for i, player in enumerate(self.input.players)
        ]
        # Add objective
        # Maximize sum of expected score of chosen players.
        # Add transfer costs.
        self.model.objective = mip.maximize(
            mip.xsum(
                x[i] * (player["expected_score"] + transfer_costs_shift_in[i] + transfer_costs_shift_out[i])
                for i, player in enumerate(self.input.players)
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

