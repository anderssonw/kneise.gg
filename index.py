import logging
from GGClient import GGClient
from tournament import BracketType
from whomst.whomst_db import Whomst
from flask import Flask, render_template, redirect, request, jsonify
from flask.logging import create_logger
from flask_caching import Cache
from itertools import groupby
from urllib.parse import unquote_plus
import time


app = Flask(__name__)
app.logger.setLevel(logging.INFO)

try:
    import uwsgi
    cache_config = {'CACHE_TYPE': 'uwsgi', 'CACHE_UWSGI_NAME': 'smashggcache', 'CACHE_DEFAULT_TIMEOUT': 60}
except ImportError:
    cache_config = {'CACHE_TYPE': 'simple'}
finally:
    cache = Cache(app, config=cache_config)
    cache.init_app(app)

#whomster = Whomst('./whomst/')
#whomster.setup_database()


@app.errorhandler(ValueError)
def handle_value_error(error):
    return 'bee boo poo pee fucko boingo in the backend' + \
        f'<br><br>{str(error)}'


@app.route('/robots.txt')
def robots():
    r = Response(response="User-Agent: *\nDisallow: /\n", status=200, mimetype="text/plain")
    r.headers["Content-Type"] = "text/plain; charset=utf-8"
    return r


@app.route('/')
def search():
    return render_template('search.jinja2')


@app.route('/tournaments')
@cache.memoize(timeout=60*60)
def coming_tournaments():
    client = GGClient(logger=app.logger)
    t = client.get_coming_tournaments()

    dates = []
    for k, g in groupby(t, lambda t: t.date.strftime('%Y-%m-%d')):
        dates.append(list(g))

    return render_template('coming_tournaments.jinja2', coming_tournaments=dates)


@app.route('/bracket/search/<string:search>')
def choose_tournament(search):
    search = unquote_plus(search)
    client = GGClient(logger=app.logger)
    tournaments = client.search_for_tournaments(search)
    if len(tournaments) == 1:
        tournament_id = tournaments[0].id
        return redirect(f'/bracket/{tournament_id}')
    return render_template('tournament.jinja2', url_path='/bracket', tournaments=tournaments, search=search)


@app.route('/bracket/<int:tournament_id>')
@cache.memoize(timeout=10*60)
def choose_event(tournament_id):
    client = GGClient(logger=app.logger)
    events = client.get_melee_events(tournament_id)
    smashggurl = client.get_smashgg_url(tournament_id, 0, 0, 0)

    if len(events) == 1:
        event_id = list(events.keys())[0]
        return redirect(f'{request.path}/{event_id}')
    return render_template('event.jinja2', url_path=request.path, events=events, smashggurl=smashggurl)


@app.route('/bracket/<int:tournament_id>/<int:event_id>')
@cache.memoize(timeout=10*60)
def choose_phase(tournament_id, event_id):
    client = GGClient(logger=app.logger)
    phases = client.get_event_phases(event_id)
    smashggurl = client.get_smashgg_url(tournament_id, event_id, 0, 0)

    if len(phases) == 1:
        phase_id = list(phases.keys())[0]
        return redirect(f'{request.path}/{phase_id}')
    return render_template('phase.jinja2', url_path=request.path, phases=phases, smashggurl=smashggurl)


@app.route('/bracket/<int:tournament_id>/<int:event_id>/<int:phase_id>')
@cache.memoize(timeout=10*60)
def choose_phase_group(tournament_id, event_id, phase_id):
    client = GGClient(logger=app.logger)
    phase_groups = client.get_phase_groups(phase_id)
    smashggurl = client.get_smashgg_url(tournament_id, event_id, phase_id, 0)

    if len(phase_groups) == 1:
        phase_group_id = phase_groups[0]['id']
        return redirect(f'{request.path}/{phase_group_id}')
    return render_template('phase_group.jinja2', url_path=request.path, phase_groups=phase_groups, smashggurl=smashggurl)


@app.route('/bracket/<int:tournament_id>/<int:event_id>/<int:phase_id>/<int:phase_group_id>')
@cache.memoize(timeout=1*60)
def render_bracket(tournament_id, event_id, phase_id, phase_group_id):
    client = GGClient(logger=app.logger)
    bracket = client.get_phase_group_bracket(phase_group_id, tournament_id)
    bracket.finalize()
    smashggurl = client.get_smashgg_url(tournament_id, event_id, phase_id, phase_group_id)

    if bracket.type in [BracketType.DOUBLE_ELIMINATION, BracketType.SINGLE_ELIMINATION]:
        return render_template('bracket.jinja2', bracket=bracket, smashggurl=smashggurl)
    elif bracket.type == BracketType.ROUND_ROBIN:
        return render_template('pool.jinja2', bracket=bracket, smashggurl=smashggurl)


@app.route('/user/<int:user_id>')
def user_tournaments(user_id):
    client = GGClient(logger=app.logger)
    user = client.get_user(user_id)

    print(user['tournaments'])

    user['upcoming'] = (filter(lambda elem: elem['startAt'] > int(time.time()) , user['tournaments']))
    user['ongoing'] = (filter(lambda elem: (elem['startAt'] < int(time.time() and elem['endAt'] > int(time.time()))) , user['tournaments']))
    user['finished'] = (filter(lambda elem: elem['endAt'] < int(time.time()) , user['tournaments']))

    return render_template('user.jinja2', user=user)

# NO WHOMST FOR YOU!!!
#@app.route('/whomst/')
#def whomst_display():
#    whomsts = whomster.fetch(100)
#    return render_template('whomst.jinja2', whomsts=whomsts)
#
#
#@app.route('/whomst/insert', methods=['POST'])
#def whomst_insert():
#    content = request.get_json(force=True, silent=True)
#
#    display_name = content['display_name']
#    connect_code = content['connect_code']
#    ip_address = content['ip_address']
#    region = content['region']
#    whomster.whomst(display_name, connect_code, ip_address, region)
#
#    return 'whomsted successfully'
#
#
#@app.route('/whomst/search/ip_address/<ip_address>', defaults={'mask': 24})
#@app.route('/whomst/search/ip_address/<ip_address>/<mask>')
#def whomst_search_ip_address(ip_address, mask):
#    whomsts = whomster.fetch_by_ip_address(ip_address, mask=int(mask), limit=100)
#    return render_template('whomst.jinja2', whomsts=whomsts)
#
#
#@app.route('/whomst/search/connect_code/<connect_code>')
#def whomst_search_connect_code(connect_code):
#    connect_code = connect_code.replace("_", "#")
#    whomsts = whomster.fetch_by_connect_code(connect_code, limit=100)
#    return render_template('whomst.jinja2', whomsts=whomsts)
#
#
#@app.route('/whomst/note', methods=['POST'])
#def whomst_note():
#    content = request.get_json(force=True, silent=True)
#    try:
#        display_name = content['display_name']
#        connect_code = content['connect_code'].replace("_", "#")
#        ip_address = content['ip_address']
#        note = content['note']
#    except Exception:
#        app.logger.info(content)
#        return "not quite right"
#
#    updated = whomster.set_note(display_name, connect_code, ip_address, note)
#    return "quite right"