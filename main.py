import pandas as pd
import secrets
from flask import Flask, render_template
from flask_caching import Cache
from flask_bootstrap import Bootstrap5
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import SubmitField, SelectMultipleField, FloatField
from wtforms.validators import DataRequired, ValidationError, NumberRange
from wtforms.widgets import html_params
from markupsafe import Markup
from data import ApiFootball, HoldetDk, Stats, TEAM_ID_MAP, EVENTS
from optimization import Optimization, OptimizationInput

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
bootstrap = Bootstrap5(app)
csrf = CSRFProtect(app)
foo = secrets.token_urlsafe(16)
app.secret_key = foo

API_FOOTBALL_KEY = "bf198eceb1b289cd1d865352a470f77f"


# TODO: add chatgpt based "feedback from assistant coach".

# Custom widget for multi-checkbox field
class CustomCheckboxWidget(object):
    def __call__(self, field, **kwargs):
        kwargs.setdefault('type', 'checkbox')
        field_id = kwargs.pop('id', field.id)
        html = [Markup('<br><br>')]
        for value, label, checked, _ in field.iter_choices():
            choice_id = f"{field_id}-{value}"
            options = dict(kwargs, name=field.name, value=value, id=choice_id)
            if checked:
                options['checked'] = 'checked'
            html.append(Markup('<input %s /> ' % html_params(**options)))
            html.append(Markup('<label for="%s">%s</label><br>' % (choice_id, label)))
        return Markup(''.join(html))


# Custom multi-checkbox field
class MultiCheckboxField(SelectMultipleField):
    widget = CustomCheckboxWidget()
    option_widget = None


def get_api_football_data():
    return ApiFootball(API_FOOTBALL_KEY)


def get_holdet_data():
    return HoldetDk()


def get_player_names():
    data = get_holdet_data()
    return [(player['player_id'], player['person_fullname']) for player in data.player_data]


def get_data(
        existing_player_ids: list,
        bank_beholdning: float,
        weight_team_win: float,
        weight_player_goals: float,
        weight_player_assists: float,
        weight_player_cards: float,
        weight_player_clean_sheets: float
):
    odds_data = get_api_football_data()
    holdet_data = get_holdet_data()
    stats = Stats()
    optimization_input = OptimizationInput(
        holdet=holdet_data,
        api_football=odds_data,
        stats=stats,
        existing_player_ids=existing_player_ids,
        bank_beholdning=bank_beholdning,
        weight_team_win=weight_team_win,
        weight_player_goals=weight_player_goals,
        weight_player_assists=weight_player_assists,
        weight_player_cards=weight_player_cards,
        weight_player_clean_sheets=weight_player_clean_sheets,
        team_id_map=TEAM_ID_MAP,
        events=EVENTS
    )
    return optimization_input


def validate_selection_count(form, field):
    if not (len(field.data) == 0 or len(field.data) == 11):
        raise ValidationError('You must select either 0 or 11 players.')


class TeamForm(FlaskForm):
    def __init__(self, choices, *args, **kwargs):
        super(TeamForm, self).__init__(*args, **kwargs)
        self.options.choices = choices

    options = MultiCheckboxField('Select existing team:', validators=[validate_selection_count])
    bank_beholdning = FloatField('Cash holding', validators=[DataRequired()])

    weight_team_win = FloatField('Team win', default=1, validators=[DataRequired(), NumberRange(min=0, max=1)])
    weight_player_goals = FloatField('Player goals', default=1, validators=[DataRequired(), NumberRange(min=0, max=1)])
    weight_player_assists = FloatField('Player assists', default=1, validators=[DataRequired(), NumberRange(min=0, max=1)])
    weight_player_cards = FloatField('Player cards', default=1, validators=[DataRequired(), NumberRange(min=0, max=1)])
    weight_player_clean_sheets = FloatField('Player clean sheets', default=1, validators=[DataRequired(), NumberRange(min=0, max=1)])

    submit = SubmitField('Optimize')


def get_optimal_team_df(
        existing_player_ids: list,
        bank_beholdning: float,
        weight_team_win: float,
        weight_player_goals: float,
        weight_player_assists: float,
        weight_player_cards: float,
        weight_player_clean_sheets: float
):
    optimization_input = get_data(
        existing_player_ids,
        bank_beholdning,
        weight_team_win,
        weight_player_goals,
        weight_player_assists,
        weight_player_cards,
        weight_player_clean_sheets
    )
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
        # Calc optimal team and render
        optimal_team_df = get_optimal_team_df(
            existing_player_ids=[int(p_id) for p_id in team_form.options.data],
            bank_beholdning=team_form.bank_beholdning.data,
            weight_team_win=team_form.weight_team_win.data,
            weight_player_goals=team_form.weight_player_goals.data,
            weight_player_assists=team_form.weight_player_assists.data,
            weight_player_cards=team_form.weight_player_cards.data,
            weight_player_clean_sheets=team_form.weight_player_clean_sheets.data
        )
        optimal_team_table = optimal_team_df.to_html(classes='table table-striped', escape=False, index=False)

    return render_template('index.html', team_form=team_form, optimal_team_table=optimal_team_table)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
