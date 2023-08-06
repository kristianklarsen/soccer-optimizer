from mip import *
import pandas as pd


class Optimization:
    """Optimization class."""

    def __init__(self, player_data: pd.DataFrame):
        self.model = Model(sense=MAXIMIZE, solver_name=CBC)
        self.player_data = player_data

    def build_model(self):

        # Add vars
        player_select_vars = []
        for idx, player in self.player_data.iterrows():
            player_select_vars.append(
                self.model.add_var(
                    name=player.person_shortname,
                    var_type=BINARY,
                    obj=1
                )
            )

        # add constraints
        self.model.add_constr(
            name="Exactly 11 players",
            lin_expr=sum(player_select_vars)==11
        )

    def run(self):
        # optimize and return results
        self.model.optimize(max_seconds=30)
