from mip import *


class Optimization:
    """Optimization class."""

    def __init__(self):
        self.model = Model(sense=MAXIMIZE, solver_name=CBC)

    def build_model(self):
        # add vars
        # add constraints
        # add obj

    def run(self):
        # optimize and return results
