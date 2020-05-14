import logging
from GGClient import GGClient
from flask import Flask, render_template, redirect, request, jsonify
from flask.logging import create_logger
from tournament import BracketType


app = Flask(__name__)
log = create_logger(app)


@app.errorhandler(ValueError)
def handle_value_error(error):
    return 'bee boo poo pee fucko boingo in the backend' + \
        f'<br><br>{str(error)}'


@app.route('/')
def search():
    return render_template('search.html')


@app.route('/bracket/search/<string:search>')
def choose_tournament(search):
    client = GGClient(logger=log)
    tournaments = client.search_for_tournaments(search)
    if len(tournaments) == 1:
        tournament_id = list(tournaments.keys())[0]
        return redirect(f'/bracket/{tournament_id}')
    return render_template('tournament.jinja2', url_path='/bracket', tournaments=tournaments, search=search)


@app.route('/bracket/<int:tournament_id>')
def choose_event(tournament_id):
    client = GGClient(logger=log)
    events = client.get_melee_events(tournament_id)
    if len(events) == 1:
        event_id = list(events.keys())[0]
        return redirect(f'{request.path}/{event_id}')
    return render_template('event.jinja2', url_path=request.path, events=events)


@app.route('/bracket/<int:tournament_id>/<int:event_id>')
def choose_phase(tournament_id, event_id):
    client = GGClient(logger=log)
    phases = client.get_event_phases(event_id)
    if len(phases) == 1:
        phase_id = list(phases.keys())[0]
        return redirect(f'{request.path}/{phase_id}')
    return render_template('phase.jinja2', url_path=request.path, phases=phases)


@app.route('/bracket/<int:tournament_id>/<int:event_id>/<int:phase_id>')
def choose_phase_group(tournament_id, event_id, phase_id):
    client = GGClient(logger=log)
    phase_groups = client.get_phase_groups(phase_id)
    if len(phase_groups) == 1:
        phase_group_id = phase_groups[0]['id']
        return redirect(f'{request.path}/{phase_group_id}')
    return render_template('phase_group.jinja2', url_path=request.path, phase_groups=phase_groups)


@app.route('/bracket/<int:tournament_id>/<int:event_id>/<int:phase_id>/<int:phase_group_id>')
def render_bracket(tournament_id, event_id, phase_id, phase_group_id):
    client = GGClient(logger=log)
    bracket = client.get_phase_group_bracket(phase_group_id, tournament_id)
    bracket.finalize()

    if bracket.type in [BracketType.DOUBLE_ELIMINATION, BracketType.SINGLE_ELIMINATION]:
        return render_template('bracket.jinja2', bracket=bracket)
    elif bracket.type == BracketType.ROUND_ROBIN:
        return render_template('pool.jinja2', bracket=bracket)


@app.route('/user/<int:user_id>')
def user_tournaments(user_id):
    client = GGClient(logger=log)
    user = client.get_user(user_id)
    return render_template('user.jinja2', user=user)
