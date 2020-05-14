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
    def __init__(self, entrant_id, entrant_name, entrant_score, prereq, index):
        self.entrant_id = entrant_id
        self.entrant_name = entrant_name
        self.entrant_score = entrant_score
        self.prereq = prereq
        self.index = index


class Set(object):
    def __init__(self, id, phase, round, display_score, winner_id, identifier, is_gf, slots):
        self.id = id
        self.phase = phase
        self.round = round
        self.display_score = display_score
        self.winner_id = winner_id
        self.identifier = identifier
        self.is_gf = is_gf

        self.slots = []
        for i, slot in enumerate(slots):
            # If there is no entrant in a slot, the entrant is not yet decided
            # (pools, previous set or similar).
            try:
                entrant_id = slot['entrant']['id']
                entrant_name = slot['entrant']['name']
            except TypeError:
                entrant_id = i
                entrant_name = ''

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

            self.slots.append(Slot(entrant_id, entrant_name, entrant_score, prereq, index))
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


class Bracket(object):
    def __init__(self, id, name='', type=None):
        self.id = id
        self.name = name
        self.type = BracketType[type]
        self.rounds = {}
        self.sets = {}
        self.upper_bracket = None
        self.lower_bracket = None


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
        self.sets[set.id] = set
        try:
            self.rounds[round].append(set)
        except KeyError:
            self.rounds[round] = []
            self.rounds[round].append(set)


    def _remove_unbalanced_rounds(self):
        # (TODO): For now we just delete unbalanced rounds, as they harder to
        # draw, and usually contain less interesting matches.
        first_ub, first_lb = min(self.ub_rounds), max(self.lb_rounds)
        for round in self.rounds.copy():
            if round in [first_ub, first_lb]:
                if (round == first_ub and len(self.ub_rounds) == 1) or \
                   (round == first_lb and len(self.lb_rounds) == 1):
                    continue

                inc = -1 if round < 0 else 1
                sets_in_round = len(self.rounds[round])
                sets_in_next_round = len(self.rounds[round+inc])

                if sets_in_round == sets_in_next_round:
                    continue

                if not math.log2(sets_in_round).is_integer() or sets_in_round == 1:
                    del self.rounds[round]


    def _connect_sets(self):
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
        # smash.gg. Seems to work.
        for set in self.sets.values():
            for slot in set.slots:
                if slot.prereq == 'set':
                    child_set = self.sets[slot.prereq.id]
                    set._add_child(child_set)
                    child_set._add_parent(self)


    def finalize_bracket_tree(self):
        if self.type != BracketType.DOUBLE_ELIMINATION:
            raise ValueError(f'Invalid bracket type {self.type}')
        self._connect_sets()
