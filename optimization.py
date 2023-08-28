import mip
from data import OptimizationInput
from typing import List


class Optimization:
    """Optimization class."""

    def __init__(self, optimization_input: OptimizationInput):
        self.model = mip.Model(solver_name=mip.CBC)
        self.input = optimization_input

    def build_model(self):

        # Add selection variable for each player, and objective coefficient expected score
        x = [
            self.model.add_var(
                name=str(player["player_id"]),
                var_type=mip.BINARY
            ) for player in self.input.players
        ]

        # Add constraints
        self.model.add_constr(
            name="Exactly 11 players",
            lin_expr=sum(x) == 11
        )
        self.model.add_constr(
            name="Formations Goalkeeper",
            lin_expr=mip.xsum(
                x[i] if player["position_name"] == "Mål" else 0 for i, player in enumerate(self.input.players)
            ) == 1
        )
        self.model.add_constr(
            name="Formations Defenders",
            lin_expr=3 <= mip.xsum(
                x[i] if player["position_name"] == "Forsvar" else 0 for i, player in enumerate(self.input.players)
            ) <= 5
        )
        self.model.add_constr(
            name="Formations Defenders",
            lin_expr=mip.xsum(
                x[i] if player["position_name"] == "Forsvar" else 0 for i, player in enumerate(self.input.players)
            ) >= 3
        )
        self.model.add_constr(
            name="Formations Midfielders",
            lin_expr=3 <= mip.xsum(
                x[i] if player["position_name"] == "Midtbane" else 0 for i, player in enumerate(self.input.players)
            ) <= 5
        )
        self.model.add_constr(
            name="Formations Midfielders",
            lin_expr=mip.xsum(
                x[i] if player["position_name"] == "Midtbane" else 0 for i, player in enumerate(self.input.players)
            ) >= 3
        )
        self.model.add_constr(
            name="Formations Attackers",
            lin_expr=mip.xsum(
                x[i] if player["position_name"] == "Angreb" else 0 for i, player in enumerate(self.input.players)
            ) <= 3
        )
        self.model.add_constr(
            name="Formations Attackers",
            lin_expr=1 <= mip.xsum(
                x[i] if player["position_name"] == "Angreb" else 0 for i, player in enumerate(self.input.players)
            ) >= 1
        )

        # Add objective
        self.model.objective = mip.maximize(
            mip.xsum(
                x[i] * player["expected_score"] for i, player in enumerate(self.input.players)
            )
        )

    def run(self):
        # optimize and return results
        self.model.optimize(max_seconds=30)

    def get_result(self) -> List[str]:
        """Returns optimum, i.e. selected players that optimizes expected score."""
        return [
            next((player["person_fullname"] for player in self.input.players if player['player_id'] == int(var.name)), None)
            for var in self.model.vars._VarList__vars if var.x == 1
        ]

