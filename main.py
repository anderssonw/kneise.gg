import inquirer
from GGClient import GGClient


def choose_event(events):
    questions = [
        inquirer.List('event',
                      message='Choose an event',
                      choices=events.values(),
        )
    ]
    event_name = inquirer.prompt(questions)['event']
    return list(events.keys())[list(events.values()).index(event_name)]


def choose_phase(phases):
    questions = [
        inquirer.List('phase',
                      message='Choose a phase',
                      choices=phases.values(),
        )
    ]
    phase_name = inquirer.prompt(questions)['phase']
    return list(phases.keys())[list(phases.values()).index(phase_name)]


def render_bracket(search):
    client = GGClient()
    events = client.search_for_event(search)
    event_id = choose_event(events)
    phases = client.get_event_phases(event_id)
    phase_id = choose_phase(phases)

    bracket = client.get_phase_bracket(phase_id)
    bracket.finalize_bracket_tree()
    bracket.render_bracket()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='smash.gg bracket viewer')
    parser.add_argument('--search')
    args = parser.parse_args()

    if args.search:
        render_bracket(args.search)

