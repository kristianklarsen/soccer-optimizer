import pandas as pd
import secrets
from flask import Flask, request, render_template
from flask_caching import Cache
from flask_bootstrap import Bootstrap5

from flask_wtf import FlaskForm, CSRFProtect
from wtforms import PasswordField, SubmitField, SelectMultipleField, SelectField
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

def get_data(existing_player_ids: list):
    odds_data = ApiFootball(API_FOOTBALL_KEY)
    holdet_data = HoldetDk()
    optimization_input = OptimizationInput(
        holdet_data, odds_data, existing_player_ids=existing_player_ids, team_id_map=TEAM_ID_MAP, events=EVENTS
    )
    return optimization_input


def get_player_names():
    data = get_data(existing_player_ids=[])
    return [(player['player_id'], player['person_fullname']) for player in data.players]


class TeamForm(FlaskForm):
    def __init__(self, choices, *args, **kwargs):
        super(TeamForm, self).__init__(*args, **kwargs)
        self.options.choices = choices

    options = SelectMultipleField('Input existing team')
    submit = SubmitField('Optimize')


def get_optimal_team_df(existing_player_ids: list):
    optimization_input = get_data(existing_player_ids)
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
    optimal_team_table = None
    choices = get_player_names()
    team_form = TeamForm(choices=choices)

    if team_form.validate_on_submit():
        existing_player_ids = team_form.options.data
        existing_player_ids = [int(p_id) for p_id in existing_player_ids]
        optimal_team_df = get_optimal_team_df(existing_player_ids)
        optimal_team_table = optimal_team_df.to_html(classes='table table-striped', escape=False, index=False)

    return render_template('index.html', team_form=team_form, optimal_team_table=optimal_team_table)


if __name__ == "__main__":
    app.run(host='0.0.0.0')
