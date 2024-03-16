import mip
import matplotlib as mpl
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image
from mplsoccer import VerticalPitch, Sbopen, FontManager, inset_image

from data import OptimizationInput


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

        # TODO: add budget constraint
        #  How to get player costs? ...

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
        players = [
                {
                    "person_fullname": next(
                        (
                            player["person_fullname"]
                            for player in self.input.players if player['player_id'] == int(var.name)
                        ),
                        None
                    ),
                    "position_name_en": next(
                        (
                            player["position_name_en"]
                            for player in self.input.players if player['player_id'] == int(var.name)
                        ),
                        None
                    ),
                    "team_name": next(
                        (
                            player["team_name"]
                            for player in self.input.players if player['player_id'] == int(var.name)
                        ),
                        None
                    ),
                }
                for var in self.model.vars._VarList__vars if var.x == 1
            ]
        formation = (
            f"{len([p for p in players if p['position_name_en'] == 'Defense'])}"
            f"{len([p for p in players if p['position_name_en'] == 'Midfielder'])}"
            f"{len([p for p in players if p['position_name_en'] == 'Striker'])}"
        )
        return {
            "optimal_team": players,
            "formation": formation,
            "expected_score": self.model.objective_value
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

