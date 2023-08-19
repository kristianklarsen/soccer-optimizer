from mip import *
from data import OptimizationInput

class Optimization:
    """Optimization class."""

    def __init__(self, opt_input: OptimizationInput):
        self.model = Model(sense=MAXIMIZE, solver_name=CBC)
        self.players = opt_input.players

    def build_model(self):

        # Add selection variable for each player
        player_select_vars = []
        for player in self.players:
            player_select_vars.append(
                self.model.add_var(
                    name=player["person_shortname"],
                    var_type=BINARY,
                    obj=0
                )
            )

        # Add constraints
        self.model.add_constr(
            name="Exactly 11 players",
            lin_expr=sum(player_select_vars)==11
        )

        # Add objective
        for player in self.players:


    def run(self):
        # optimize and return results
        self.model.optimize(max_seconds=30)
