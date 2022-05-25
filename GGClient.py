import json
from operator import itemgetter
import tournament as tournament
import requests
from datetime import datetime
import pytz
from urllib.parse import urlparse
from python_graphql_client import GraphqlClient
from algoliasearch.search_client import SearchClient
import os
from dotenv import load_dotenv
load_dotenv()


class GGConstant(object):
    melee_type = 1


class GGClient(object):
    def __init__(self, api_endpoint='https://api.start.gg/gql/alpha', logger=None):
        self.api_endpoint = api_endpoint
        self.logger = logger
        self.gql_client = GraphqlClient(self.api_endpoint)
        self.user_agent = 'Mozilla/5.0'
        self.headers = {
            'User-Agent': self.user_agent,
            'client-version': '20',
            'Authorization': 'Bearer ' + os.getenv('SMASHGG_API_KEY')
        }


    def log_gql_execution(self, gql):
        if self.logger is None:
            return

        log_str = gql.strip().partition('\n')[0]
        self.logger.info(f'Executed gql: {log_str}')


    def _execute_gql(self, gql, variables):
        result = self.gql_client.execute(gql, variables=variables, headers=self.headers)
        content = result
        self.log_gql_execution(gql)
        return content


    def _execute_rest(self, url):
        r = requests.get(url, headers=self.headers)
        if r.status_code != 200:
            raise ValueError(f'Received {r.status_code} status code from {url}')
        return json.loads(r.text)


    def get_melee_tournaments(self, tournament_name):
        gql = \
            """
            query MeleeTournamentsByName($name: String!) {
              tournaments(query: {
                page: 1
                sortBy: "startAt desc"
                filter: {
                  name: $name,
                  videogameIds: [
                    1
                  ]
                }
              }) {
                nodes {
                  id
                  name
                  slug
                  startAt
                }
              }
            },
            """
        r = self._execute_gql(gql, {'name': tournament_name})
        tournaments = r['data']['tournaments']['nodes']
        
        tournaments_out = []
        for t in tournaments:
            id = t['id']
            name = t['name']
            date = datetime.fromtimestamp(t['startAt'], pytz.timezone('Europe/Oslo'))
            tournaments_out.append(tournament.Tournament(id, name, date))

        return tournaments_out

    def _rest_tournament_search(self, tournament_url):
        tournament_json = self._execute_rest(tournament_url)['entities']['tournament']
        tournament = {tournament_json['id']: tournament_json['name']}
        return tournament


    def _parse_smashgg_tournament_url(self, original_url):
        # We've replaced / with _, a common custom for having links as url
        # variables.
        url = original_url.replace("_", "/")
        api_url = url.replace("smash.gg", "api.smash.gg")

        parsed_url = urlparse(api_url)
        url_base = parsed_url.netloc
        url_path = parsed_url.path
        url_path = url_path.split("/")

        try:
            if url_base:
                return f'https://{url_base}/{url_path[1]}/{url_path[2]}'
            else:
                return f'https://{url_path[0]}/{url_path[1]}/{url_path[2]}'
        except:
            raise ValueError(f'Could not parse url: {url}')


    def get_coming_tournaments(self):
        api_url = 'https://smash.gg/api/-/gg_api./public/tournaments/schedule;'
        filter = 'filter=%7B%22upcoming%22%3Atrue%2C%22videogameIds%22%3A1%7D;'
        r = self._execute_rest(f'{api_url}{filter}')

        tournaments = []
        for t in r['items']['entities']['tournament']:
            id = t['id']
            name = t['name']
            date = datetime.fromtimestamp(t['startAt'], pytz.timezone('Europe/Oslo'))
            tournaments.append(tournament.Tournament(id, name, date))

        return tournaments


    def search_for_tournaments(self, tournament_name):
        if "smash.gg_tournament" in tournament_name:
            search_url = tournament_name.strip()
            full_url = self._parse_smashgg_tournament_url(search_url)
            return self._rest_tournament_search(full_url)
        else:
            return self.get_melee_tournaments(tournament_name)

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
                    wave {
                      startAt
                    }
                    seeds(query: {sortBy: "seedNum"}) {
                      nodes {
                        entrant {
                          participants {
                            gamerTag
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
            'phaseId': phase_id,
            'page': 1,
            'perPage': 999,
        }
        result = self._execute_gql(gql, variables)
        phase_groups = result['data']['phase']['phaseGroups']['nodes']
        for phase_group in phase_groups:
          if phase_group['wave']:
            dateTime = datetime.fromtimestamp(phase_group['wave']['startAt'], pytz.timezone('Europe/Oslo'))
            phase_group['wave']['startAt'] = (dateTime.strftime('%d-%m-%y, %H:%M, %Z'))
        return phase_groups


    def get_phase_group_bracket(self, phase_group_id, tournament_id):
        gql = \
            """
            query bracket($phaseGroupId: ID!, $page: Int!, $perPage: Int!, $profileId: ID!) {
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
                    completedAt
                    stream {
                      streamName
                      streamSource
                    }
                    slots {
                      prereqId
                      prereqType
                      slotIndex
                      entrant {
                        id
                        participants {
                          id
                          gamerTag
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
              tournament(id: $profileId) {
                name
              }
            }
            """
        variables = {
            'phaseGroupId': phase_group_id,
            'page': 1,
            'perPage': 999,
            'profileId': tournament_id
        }
        result = self._execute_gql(gql, variables)
        phase_group = result['data']['phaseGroup']

        if phase_group['sets']['pageInfo']['total'] == 0:
            raise ValueError(f'Bracket for "{phase_group["phase"]["name"]}" not started')

        bracket_name = phase_group['phase']['name']
        bracket_type = phase_group['bracketType']
        tournament_name = result['data']['tournament']['name']
        bracket = tournament.Bracket(phase_group_id, bracket_name, bracket_type, tournament_name)

        for set in phase_group['sets']['nodes']:
            stream = None
            if set['stream']:
              if set['stream']['streamSource'] == 'TWITCH':
                stream = 'https://twitch.tv/'+set['stream']['streamName']
            set_params = {
                'id': set['id'],
                'phase': phase_group_id,
                'round': set['round'],
                'display_score': set['displayScore'],
                'winner_id': set['winnerId'],
                'identifier': set['identifier'],
                'is_gf': set['wPlacement'] == 1,
                'completed': set['completedAt'] is not None,
                'slots': set['slots'],
                'stream': stream
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
                user {
                  tournaments (query: {
                    filter: {
                      videogameId: [1]
                    }
                  }) {
                    nodes {
                      id
                      name
                      startAt
                      endAt
                    }
                  }
                }
              }
            }
            """
        r = self._execute_gql(gql, { 'id': user_id } )['data']['participant']
        tournaments = r['user']['tournaments']['nodes']
        tournaments.sort(key=lambda node: node['startAt'], reverse=True)

        #for t in tournaments:
        #  dateTime = datetime.fromtimestamp(t['startAt'], pytz.timezone('Europe/Oslo'))
        #  t['startAt'] = (dateTime.strftime('%d-%m-%y, %H:%M, %Z'))


        user = {}
        user['tournaments'] = tournaments
        user['gamerTag'] = r['gamerTag']
        user['id'] = r['id']


        print(user)


        return user

    def get_smashgg_url(self, tournament_id, event_id, phase_id, phase_group_id):
      gql = \
            """
            query urlComponents($profileId: ID!, $eventId: ID!) {
              tournament(id: $profileId) {
                slug
              }
              event(id: $eventId) {
                slug
              }
            }
            """
      variables = {
        'profileId': tournament_id,
        'eventId': event_id,
      }

      result = self._execute_gql(gql, variables)['data']

      url = 'smash.gg/'
      
      if result['event']:
        url += result['event']['slug']
        if phase_id != 0:
          url += '/brackets/'+str(phase_id)
          if phase_group_id != 0:
            url += '/'+str(phase_group_id)
      elif result['tournament']:
        url += result['tournament']['slug']
      
      return url
