import mip
from mip import *
from data import OptimizationInput


class Optimization:
    """Optimization class."""

    def __init__(self, optimization_input: OptimizationInput):
        self.model = Model(solver_name=CBC)
        self.input = optimization_input

    def build_model(self):

        # Add selection variable for each player, and objective coefficient expected score
        x = [
            self.model.add_var(
                name=str(player["player_id"]),
                var_type=BINARY
            ) for player in self.input.players
        ]

        # Add constraints
        self.model.add_constr(
            name="Exactly 11 players",
            lin_expr=sum(x)==11
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

