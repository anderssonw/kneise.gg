import json
import tournament
from graphqlclient import GraphQLClient
from algoliasearch.search_client import SearchClient


class GGConstant(object):
    melee_type = 1


class GGClient(object):
    def __init__(self, api_endpoint='https://smash.gg/api/-/gql', logger=None):
        self.api_endpoint = api_endpoint
        self.logger = logger
        self.gql_client = GraphQLClient(self.api_endpoint)
        self.algolia_file = 'algolia.json'
        self.user_agent = 'Mozilla/5.0'
        self.headers = {
            'User-Agent': self.user_agent,
            'client-version': 15,
        }


    def log_gql_execution(self, gql):
        if self.logger is None:
            return

        log_str = gql.strip().partition('\n')[0]
        self.logger.info(f'Executed gql: {log_str}')


    def _execute_gql(self, gql, variables):
        result = self.gql_client.execute(gql, variables=variables, headers=self.headers)
        content = json.loads(result)
        self.log_gql_execution(gql)
        return content


    def search_for_tournaments(self, tournament_name):
        with open(self.algolia_file, 'r') as f:
            algolia = json.loads(f.read())

        client = SearchClient.create(algolia['application-id'], algolia['api-key'])
        index = client.init_index('omnisearch')
        objects = index.search(tournament_name)

        if len(objects['hits']) == 0:
            raise ValueError(f'Tournament "{tournament_name}" not found')

        tournaments = {}
        for tournament in objects['hits']:
            id = tournament['profileId']
            name = tournament['_highlightResult']['name']['value']
            name = name.replace('<em>', '').replace('</em>', '')
            tournaments[id] = name
        return tournaments


    def get_melee_events(self, tournament_id):
        gql = \
            """
            query tournament($profileId: ID!) {
              tournament(id: $profileId) {
                name
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
        response = self._execute_gql(gql, {'profileId': tournament_id})
        melee_events = {}
        for event in response['data']['tournament']['events']:
            if event['videogame']['id'] == GGConstant.melee_type:
                melee_events[event['id']] = event['name']


        if not melee_events:
            tournament_name = response['data']['tournament']['name']
            raise ValueError(f'Melee event not found for {tournament_name}') from None
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


    def get_phase_groups(self, phase_id):
        gql = \
            """
            query phase($phaseId: ID!) {
              phase(id: $phaseId) {
                phaseGroups {
                  nodes {
                    id
                    displayIdentifier
                    bracketType
                    seeds(query: {sortBy: "seedNum"}) {
                      nodes {
                        entrant {
                          name
                        }
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
        result = self._execute_gql(gql, variables)
        phase_groups = result['data']['phase']['phaseGroups']['nodes']
        return phase_groups


    def get_phase_group_bracket(self, phase_group_id):
        gql = \
            """
            query bracket($phaseGroupId: ID!, $page: Int!, $perPage: Int!) {
              phaseGroup(id: $phaseGroupId) {
                bracketType
                phase {
                  name
                }
                sets(page: $page, perPage: $perPage, sortType: STANDARD) {
                  pageInfo {
                    total
                  }
                  nodes {
                    id
                    round
                    displayScore
                    winnerId
                    identifier
                    wPlacement
                    slots {
                      prereqId
                      prereqType
                      slotIndex
                      entrant {
                        id
                        name
                        participants {
                          id
                        }
                        seeds {
                          seedNum
                          phaseGroup {
                            id
                          }
                        }
                      }
                      standing {
                        stats {
                          score {
                            value
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        variables = {
            'phaseGroupId': phase_group_id,
            'page': 1,
            'perPage': 999,
        }
        phase_group = self._execute_gql(gql, variables)['data']['phaseGroup']

        if phase_group['sets']['pageInfo']['total'] == 0:
            raise ValueError(f'Bracket for "{phase_group["phase"]["name"]}" not started')

        bracket_name = phase_group['phase']['name']
        bracket_type = phase_group['bracketType']
        bracket = tournament.Bracket(phase_group_id, bracket_name, bracket_type)

        for set in phase_group['sets']['nodes']:
            set_params = {
                'id': set['id'],
                'phase': phase_group_id,
                'round': set['round'],
                'display_score': set['displayScore'],
                'winner_id': set['winnerId'],
                'identifier': set['identifier'],
                'is_gf': set['wPlacement'] == 1,
                'slots': set['slots'],
            }
            bracket.add_set(**set_params)

        return bracket


    def get_user(self, user_id):
        gql = \
            """
            query user_tournaments($id: ID!) {
              participant(id: $id) {
                id
                gamerTag
                otherTournamentsCount
                otherTournaments {
                  id
                  name
                }
              }
            }
            """
        user = self._execute_gql(gql, { 'id': user_id } )['data']['participant']
        return user
