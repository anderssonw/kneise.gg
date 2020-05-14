import json
import math
from anytree import Node, RenderTree
from collections import defaultdict, deque
from enum import Enum


class BracketType(Enum):
    DOUBLE_ELIMINATION = 0
    ROUND_ROBIN = 1
    SINGLE_ELIMINATION = 2
    SWISS = 3
    EXHIBITION = 4
    CUSTOM_SCHEDULE = 5
    MATCHMAKING = 6
    ELIMINATION_ROUNDS = 7
    RACE = 8


class Prereq(object):
    def __init__(self, id, type):
        self.id = id
        self.type = type


class Slot(object):
    def __init__(self, entrant, prereq, index):
        self.entrant = entrant
        self.prereq = prereq
        self.index = index


class Entrant(object):
    def __init__(self, id, participant_id, name, score, seed):
        self.id = id
        self.participant_id = participant_id
        self.name = name
        self.score = score
        self.seed = seed


class Set(object):
    def __init__(self, id, phase_group_id, round, display_score, winner_id, identifier, is_gf, slots):
        self.id = id
        self.phase_group_id = phase_group_id
        self.round = round
        self.display_score = display_score
        self.winner_id = winner_id
        self.identifier = identifier
        self.is_gf = is_gf

        self.slots = []
        self.entrants = []
        for i, slot in enumerate(slots):
            # If there is no entrant in a slot, the entrant is not yet decided
            # (pools, previous set or similar).
            try:
                entrant_id = slot['entrant']['id']
                participant_id = slot['entrant']['participants'][0]['id']
                entrant_name = slot['entrant']['name']
                entrant_seeds = slot['entrant']['seeds']
                for seed in entrant_seeds:
                    if seed['phaseGroup']['id'] == phase_group_id:
                        entrant_seed = seed['seedNum']
            except TypeError:
                entrant_id = i
                participant_id = 3817930
                entrant_name = ''
                entrant_seed = 0

            # If we have an entrant, they may have no updated score yet, making
            # their score 0. If no entrant, then the set hasn't begun.
            try:
                entrant_score = slot['standing']['stats']['score']['value'] or 0
            except TypeError:
                entrant_score = '-'

            prereq_id = int(slot['prereqId'])
            prereq_type = slot['prereqType']
            prereq = Prereq(prereq_id, prereq_type)
            index = slot['slotIndex']

            entrant = Entrant(entrant_id, participant_id, entrant_name, entrant_score, entrant_seed)
            self.slots.append(Slot(entrant, prereq, index))

            # For creating pools later, where we can do a lookup to determine
            # the order of the scoring. Not optimal.
            if entrant_id == self.winner_id:
                self.winner_seed = entrant_seed
                self.winner_score = entrant_score
            else:
                self.loser_seed = entrant_seed
                self.loser_score = entrant_score
        self.slots.sort(key=lambda s: s.index)

        self.upper_slot = self.slots[0]
        self.lower_slot = self.slots[1]

        self._parent = None
        self._children = {}


    def __str__(self):
        return f'Set ended: {self.display_score}'


    def _add_parent(self, set):
        self._parent = set


    def _add_child(self, set):
        self._children[set.id] = set


    def connect(self, next_round):
        for next_round_set in next_round:
            if self.winner_id in next_round_set.slots:
                self._add_parent(next_round_set)
                next_round_set._add_child(self)
                break


class PoolResult(object):
    def __init__(self, left_score, right_score):
        self.left_score = left_score
        self.right_score = right_score
        self.is_win = left_score > right_score
        self.dq = self.left_score == -1 or self.right_score == -1


class Bracket(object):
    def __init__(self, id, name='', type=None, tournament_name=''):
        self.id = id
        self.name = name
        self.type = BracketType[type]
        self.tournament_name = tournament_name
        self.rounds = {}
        self.sets = {}
        self.entrants = {}


    def get_rounds(self):
        return sorted(self.rounds.keys())


    @property
    def ub_rounds(self):
        return [r for r in self.get_rounds() if r > 0]


    @property
    def lb_rounds(self):
        return list(reversed([r for r in self.get_rounds() if r < 0]))


    @property
    def grand_final(self):
        return self.rounds[max(self.get_rounds())][0]


    @property
    def losers_final(self):
        return self.rounds[min(self.get_rounds())][0]


    def add_set(self, id, phase, round, display_score, winner_id, identifier, is_gf, slots):
        set = Set(id, phase, round, display_score, winner_id, identifier, is_gf, slots)

        # Add to smorgasbord for all sets.
        self.sets[set.id] = set

        # Add to correct round.
        try:
            self.rounds[round].append(set)
        except KeyError:
            self.rounds[round] = []
            self.rounds[round].append(set)

        # Add entrants of the set.
        for slot in set.slots:
            if slot.entrant.id not in self.entrants:
                self.entrants[slot.entrant.id] = slot.entrant


    def __remove_unbalanced_rounds(self, rounds):
        if len(rounds) in [0, 1]:
            return

        is_ub = all(r > 0 for r in rounds)
        first_round = min(rounds) if is_ub else max(rounds)
        inc = 1 if is_ub else -1

        if len(self.rounds[first_round]) == len(self.rounds[first_round+inc]) or \
           len(self.rounds[first_round]) == len(self.rounds[first_round+inc])*2:
            return

        del self.rounds[first_round]


    def _remove_unbalanced_rounds(self):
        self.__remove_unbalanced_rounds(self.ub_rounds)
        self.__remove_unbalanced_rounds(self.lb_rounds)


    def _connect_bracket_sets(self):
        # Sort each round by set identifier to replicate smash.gg exactly. First
        # sorts by length, and then alphabetically, e.g. X -> Y -> Z -> AA.
        def set_sort_key(set):
            return len(set.identifier), set.identifier.lower()
        for round in self.rounds.values():
            round.sort(key=set_sort_key)

        # Just remove them; usually not particularly interesting.
        self._remove_unbalanced_rounds()

        # If grand final had a reset, move the second set to its own round.
        gf_round = max(self.get_rounds())
        gf_sets = self.rounds[gf_round]
        if len(gf_sets) > 1 and gf_sets[0].is_gf:
            self.rounds[gf_round] = [gf_sets[0]]
            self.rounds[gf_round+1] = []
            self.rounds[gf_round+1].append(gf_sets[1])

        # Connect sets to previous sets using the prereq identifier from
        # smash.gg. Not used for anything at the moment, but we might need to
        # know which sets lead to where in the future.
        for set in self.sets.values():
            for slot in set.slots:
                if slot.prereq == 'set':
                    child_set = self.sets[slot.prereq.id]
                    set._add_child(child_set)
                    child_set._add_parent(self)


    def _finalize_pools(self):
        # (TODO): Dont duplicate entrants, this is a suspicious approach.
        # If anyone has the same seed, replace one with an increment of
        # 0.5.
        seeds = {}
        for set in self.sets.values():
            for slot in set.slots:
                entrant = slot.entrant
                if entrant.id in seeds:
                    entrant.seed = seeds[entrant.id]
                else:
                    if entrant.seed in seeds.values():
                        entrant.seed += 0.5
                    seeds[entrant.id] = entrant.seed

        def entrant_sort_key(entrant):
            return entrant.seed, entrant.name
        pool_entrants = list(self.entrants.values())
        pool_entrants.sort(key=entrant_sort_key)

        seed_translation = {}
        for i, entrant in enumerate(pool_entrants):
            seed_translation[entrant.seed] = i

        # print([(e.seed, e.name) for e in pool_entrants])
        self.pool_entrants = [entrant.name for entrant in pool_entrants]
        self.pool_sets = [[0]*len(self.pool_entrants) for _ in self.pool_entrants]
        for set in self.sets.values():
            if set.slots[0].entrant.id == set.winner_id:
                winner = set.slots[0].entrant
                loser = set.slots[1].entrant
            else:
                winner = set.slots[1].entrant
                loser = set.slots[0].entrant

            winner_index = seed_translation[winner.seed]
            loser_index = seed_translation[loser.seed]
            self.pool_sets[winner_index][loser_index] = PoolResult(winner.score, loser.score)
            self.pool_sets[loser_index][winner_index] = PoolResult(loser.score, winner.score)


    def finalize(self):
        if self.type == BracketType.DOUBLE_ELIMINATION:
            self._connect_bracket_sets()
            return
        elif self.type == BracketType.SINGLE_ELIMINATION:
            self._connect_bracket_sets()
            return
        elif self.type == BracketType.ROUND_ROBIN:
            self._finalize_pools()
            return
        else:
            raise ValueError(f'Invalid bracket type {self.type}')
