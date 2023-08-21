from mip import *
from data import OptimizationInput


class Optimization:
    """Optimization class."""

    def __init__(self, optimization_input: OptimizationInput):
        self.model = Model(sense=MAXIMIZE, solver_name=CBC)
        self.input = optimization_input

    def build_model(self):

        # Add selection variable for each player, and objective coefficient expected score
        x = []
        for player in self.input.players:
            x.append(
                self.model.add_var(
                    name=str(player["player_id"]),
                    var_type=BINARY,
                    obj=0
                )
            )

        # Add constraints
        self.model.add_constr(
            name="Exactly 11 players",
            lin_expr=sum(x)==11
        )

        # Add objective
        self.model.objective = xsum(
            x[i] * self.input.players[i]["expected_score"] for i in range(len(x))
        )

    def run(self):
        # optimize and return results
        self.model.optimize(max_seconds=30)
