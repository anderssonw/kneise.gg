from GGClient import GGClient
from flask import Flask, render_template, redirect, request, jsonify


app = Flask(__name__)


@app.errorhandler(ValueError)
def handle_value_error(error):
    return 'bee boo poo pee fucko boingo in the backend' + \
        f'<br><br>{str(error)}'


@app.route('/')
def search():
    return render_template('search.jinja2')


@app.route('/bracket/search/<string:search>')
def choose_tournament(search):
    client = GGClient()
    tournaments = client.search_for_tournaments(search)
    if len(tournaments) == 1:
        tournament_id = list(tournaments.keys())[0]
        return redirect(f'/bracket/{tournament_id}')
    print(tournaments)
    return render_template('tournament.jinja2', url_path='/bracket', tournaments=tournaments)


@app.route('/bracket/<int:tournament_id>')
def choose_event(tournament_id):
    client = GGClient()
    events = client.get_melee_events(tournament_id)
    if len(events) == 1:
        event_id = list(events.keys())[0]
        return redirect(f'{request.path}/{event_id}')
    return render_template('event.jinja2', url_path=request.path, events=events)


@app.route('/bracket/<int:tournament_id>/<int:event_id>')
def choose_phase(tournament_id, event_id):
    client = GGClient()
    phases = client.get_event_phases(event_id)
    if len(phases) == 1:
        phase_id = list(phases.keys())[0]
        return redirect(f'{request.path}/{phase_id}')
    return render_template('phase.jinja2', url_path=request.path, phases=phases)


@app.route('/bracket/<int:tournament_id>/<int:event_id>/<int:phase_id>')
def choose_phase_group(tournament_id, event_id, phase_id):
    client = GGClient()
    phase_groups = client.get_phase_groups(phase_id)
    if len(phase_groups) == 1:
        phase_group_id = phase_groups[0]['id']
        return redirect(f'{request.path}/{phase_group_id}')
    return render_template('phase_group.jinja2', url_path=request.path, phase_groups=phase_groups)


@app.route('/bracket/<int:tournament_id>/<int:event_id>/<int:phase_id>/<int:phase_group_id>')
def render_bracket(tournament_id, event_id, phase_id, phase_group_id):
    client = GGClient()
    bracket = client.get_phase_group_bracket(phase_group_id)
    bracket.finalize_bracket_tree()
    return render_template('bracket.jinja2', bracket=bracket)
