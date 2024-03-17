import pandas as pd
import secrets
from flask import Flask, request, redirect, url_for, render_template
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


# TODO: add chatgpt based "feedback from assistant coach".


class ApiFootballKey(FlaskForm):
    key = PasswordField('Please submit api-football key:', validators=[DataRequired(), Length(30, 50)])
    submit = SubmitField('Submit')


@cache.cached(timeout=600)
def _get_data(api_football_key: str):
    odds_data = ApiFootball(api_football_key)
    holdet_data = HoldetDk()
    optimization_input = OptimizationInput(holdet_data, odds_data, team_id_map=TEAM_ID_MAP, events=EVENTS)
    return optimization_input


def get_optimal_team_df(api_football_key):
    optimization_input = _get_data(api_football_key)
    optimization = Optimization(optimization_input)
    optimization.build_model()
    optimization.run()
    r = optimization.get_result()
    optimal_team_df = pd.DataFrame(r['optimal_team'])
    return optimal_team_df


@app.route('/', methods=['GET', 'POST'])
def index():
    form = ApiFootballKey()
    optimal_team_table = None

    if form.validate_on_submit():
        key = form.key.data
        optimal_team_df = get_optimal_team_df(key)
        optimal_team_table = optimal_team_df.to_html(classes='table table-striped', escape=False)

    return render_template('index.html', form=form, optimal_team_table=optimal_team_table)


@app.route("/optimize")
def print_optimal_team():
    api_football_key = request.args.get('key')
    optimal_team_df = get_optimal_team_df(api_football_key)
    return optimal_team_df.to_html()


if __name__ == "__main__":
    app.run()
