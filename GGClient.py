import json
import tournament
from graphqlclient import GraphQLClient
from algoliasearch.search_client import SearchClient


class GGConstant(object):
    melee_type = 1


class GGClient(object):
    def __init__(self, api_endpoint='https://smash.gg/api/-/gql'):
        self.api_endpoint = api_endpoint
        self.gql_client = GraphQLClient(self.api_endpoint)
        self.algolia_file = 'algolia.json'
        self.user_agent = 'Mozilla/5.0'
        self.headers = {
            'User-Agent': self.user_agent,
            'client-version': 15,
        }


    def _execute_gql(self, gql, variables):
        result = self.gql_client.execute(gql, variables=variables, headers=self.headers)
        content = json.loads(result)
        return content


    def search_for_event(self, event_name):
        with open(self.algolia_file, 'r') as f:
            algolia = json.loads(f.read())

        client = SearchClient.create(algolia['application-id'], algolia['api-key'])
        index = client.init_index('omnisearch')
        objects = index.search(event_name)

        if len(objects['hits']) == 0:
            raise ValueError(f'Event "{event_name}" not found')

        tournament_id = objects['hits'][0]['profileId']
        melee_events = self._get_melee_events(tournament_id)
        return melee_events


    def _get_melee_events(self, tournament_id):
        gql = \
            """
            query tournament($profileId: ID!) {
              tournament(id: $profileId) {
                events {
                  id
                  name
                  videogame {
                    id
                  }
                }
              }
            }
            """
        events = self._execute_gql(gql, {'profileId': tournament_id})
        melee_events = {}
        for event in events['data']['tournament']['events']:
            if event['videogame']['id'] == GGConstant.melee_type:
                melee_events[event['id']] = event['name']

        if not melee_events:
            raise ValueError(f'Melee event not found for {tournament_id}') from None
        return melee_events


    def get_event_phases(self, event_id):
        gql = \
            """
            query event($eventId: ID!) {
              event(id: $eventId) {
                name
                phases {
                  id
                  name
                }
                tournament {
                  name
                }
              }
            }
            """
        result = self._execute_gql(gql, {'eventId': event_id})
        phases = result['data']['event']['phases']
        phase_ids = {p['id']: p['name'] for p in phases}
        return phase_ids


    def get_phase_bracket(self, phase_id):
        gql = \
            """
            query bracket($phaseId: ID!, $page: Int!, $perPage: Int!) {
              phase(id: $phaseId) {
                name
                sets(page: $page, perPage: $perPage, sortType: STANDARD) {
                  pageInfo {
                    total
                  }
                  nodes {
                    id
                    round
                    displayScore
                    winnerId
                    slots {
                      entrant {
                        id
                        name
                      }
                    }
                  }
                }
              }
            }
            """
        variables = {
            'phaseId': phase_id,
            'page': 1,
            'perPage': 999,
        }
        phase = self._execute_gql(gql, variables)['data']['phase']

        bracket = tournament.Bracket(phase_id, phase['name'])
        for set in phase['sets']['nodes']:
            id = set['id']
            round = set['round']
            score = set['displayScore']
            winner_id = set['winnerId']
            entrants = {e['entrant']['id']: e['entrant']['name'] for e in set['slots']}
            bracket.add_set(id, phase_id, round, score, winner_id, entrants)

        return bracket
