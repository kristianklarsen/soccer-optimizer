import pandas as pd
from flask import Flask, request
from flask_caching import Cache

from data import ApiFootball, HoldetDk, TEAM_ID_MAP, EVENTS
from optimization import Optimization, OptimizationInput

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# TODO: add chatgpt based "feedback from assistant coach".

@cache.cached(timeout=600)
def _get_data(api_football_key: str):
    odds_data = ApiFootball(api_football_key)
    holdet_data = HoldetDk()
    optimization_input = OptimizationInput(holdet_data, odds_data, team_id_map=TEAM_ID_MAP, events=EVENTS)
    return optimization_input


@app.route("/optimize")
def print_optimal_team():
    api_football_key = request.args.get('key')
    optimization_input = _get_data(api_football_key)
    optimization = Optimization(optimization_input)
    optimization.build_model()
    optimization.run()
    r = optimization.get_result()
    return pd.DataFrame(r['optimal_team']).to_html()


if __name__ == "__main__":
    app.run()
