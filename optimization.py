import mip
from data import OptimizationInput
from typing import List, Dict


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

    def get_result(self) -> Dict:
        """Returns optimum, i.e. selected players that optimizes expected score."""
        return {
            "optimal_team": [
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
            ],
            "expected_score": self.model.objective_value
        }
