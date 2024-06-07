import pandas as pd
import secrets
from flask import Flask, request, render_template
from flask_caching import Cache
from flask_bootstrap import Bootstrap5

from flask_wtf import FlaskForm, CSRFProtect
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
from data import ApiFootball, HoldetDk, TEAM_ID_MAP, EVENTS
from optimization import Optimization, OptimizationInput

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
bootstrap = Bootstrap5(app)
csrf = CSRFProtect(app)
foo = secrets.token_urlsafe(16)
app.secret_key = foo

API_FOOTBALL_KEY = "bf198eceb1b289cd1d865352a470f77f"


# TODO: add chatgpt based "feedback from assistant coach".


class Button(FlaskForm):
    # TODO: add intelligent validation by test of key using https://www.api-football.com/documentation-v3#section/Authentication/API-SPORTS-Account
    #  or ditch this and hardcode key to internal and extend cache?
    submit = SubmitField('Optimize')


@cache.cached(timeout=600)
def _get_data():
    odds_data = ApiFootball(API_FOOTBALL_KEY)
    holdet_data = HoldetDk()
    optimization_input = OptimizationInput(holdet_data, odds_data, team_id_map=TEAM_ID_MAP, events=EVENTS)
    return optimization_input


def get_optimal_team_df():
    optimization_input = _get_data()
    optimization = Optimization(optimization_input)
    optimization.build_model()
    optimization.run()
    r = optimization.get_result()
    optimal_team_df = pd.DataFrame(r['optimal_team'])
    # Order by position
    sort_order = {'Goalkeeper': 0, 'Defense': 1, 'Midfielder': 2, 'Striker': 3}
    optimal_team_df.sort_values(by=['position_name_en'], key=lambda x: x.map(sort_order), inplace=True)
    return optimal_team_df


@app.route('/', methods=['GET', 'POST'])
def index():
    form = Button()
    optimal_team_table = None

    if form.validate_on_submit():
        optimal_team_df = get_optimal_team_df()
        optimal_team_table = optimal_team_df.to_html(classes='table table-striped', escape=False)

    return render_template('index.html', form=form, optimal_team_table=optimal_team_table)


@app.route("/optimize")
def print_optimal_team():
    optimal_team_df = get_optimal_team_df()
    return optimal_team_df.to_html()


if __name__ == "__main__":
    app.run()
