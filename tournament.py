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


class Entrant(object):
    def __init__(self, id, name, score):
        self.id = id
        self.name = name
        self.score = score


class Set(object):
    def __init__(self, id, phase, round, display_score, winner_id, is_grand_final, slots):
        self.id = id
        self.phase = phase
        self.round = round
        self.display_score = display_score
        self.winner_id = winner_id
        self.is_grand_final = is_grand_final

        self.entrants = {}
        for i, slot in enumerate(slots):
            id = slot['entrant']['id']
            name = slot['entrant']['name']
            score = slot['standing']['stats']['score']['value']
            self.entrants[id] = Entrant(id, name, score)

        entrants = list(self.entrants.values())
        self.upper_entrant = entrants[0]
        self.lower_entrant = entrants[1]

        self._parent = None
        self._children = {}
        self.node = None


    def __str__(self):
        return f'Set ended: {self.display_score}'


    def _add_parent(self, set):
        self._parent = set


    def _add_child(self, id, set):
        self._children[id] = set


    def connect(self, next_round):
        for next_round_set in next_round:
            if self.winner_id in next_round_set.entrants:
                self._add_parent(next_round_set)
                next_round_set._add_child(self.id, self)
                break


    def nodify(self):
        if self.node is None:
            parent = self._parent.node if self._parent else None
            self.node = Node(self, parent=parent)


class Bracket(object):
    def __init__(self, id, name='', type=None):
        self.id = id
        self.name = name
        self.type = BracketType[type]
        self.sets = defaultdict(list)
        self.upper_bracket = None
        self.lower_bracket = None


    def __str__(self):
        repr = f'Bracket for {self.id}, {self.name}, {self.num_sets} sets played\n'
        for round in self.sets:
            if round < 0:
                continue
            repr += f'  Round {round}\n'
            for set in self.sets[round]:
                repr += f'  \tSet ended: {set.display_score}\n'
        return repr[:-1]


    @property
    def num_sets(self):
        return sum(len(round) for round in self.sets.values())


    @property
    def last_round(self):
        return max(self.sets.keys())


    @property
    def ub_rounds(self):
        return sorted([round for round in self.sets.keys() if round > 0])


    @property
    def lb_rounds(self):
        return list(reversed(sorted([round for round in self.sets.keys() if round < 0])))


    @property
    def grand_final(self):
        return self.sets[self.last_round][0]


    @property
    def losers_final(self):
        return self.sets[min(self.sets.keys())][0]


    def add_set(self, id, phase, round, display_score, winner_id, is_grand_final, slots):
        set = Set(id, phase, round, display_score, winner_id, is_grand_final, slots)
        self.sets[round].append(set)


    def _reorder_rounds(self, first_round, last_round):
        is_upper_bracket = first_round > 0
        new_bracket = defaultdict(list)
        new_bracket[first_round] = self.sets[first_round]

        inc = 1 if is_upper_bracket else -1
        for round in range(first_round, last_round, inc):
            halved_next_round = len(self.sets[round]) == len(self.sets[round+inc])
            if halved_next_round:
                set_range = range(0, len(self.sets[round]))
            else:
                set_range = range(0, len(self.sets[round]), 2)
            for set in set_range:
                new_bracket[round+inc].append(new_bracket[round][set]._parent)

            # If this is the first round, we must ensure that we also move
            # second child of the sets in the next round to their correct
            # position. This is done automatically for all other rounds.
            if round == first_round and not halved_next_round:
                new_round = new_bracket[first_round][:]
                for set_index in range(1, len(self.sets[round]), 2):
                    set = new_bracket[round][set_index]
                    parent_index = new_bracket[round+inc].index(set._parent)
                    new_round[parent_index*2+1] = set
                new_bracket[round] = new_round

            # (TODO): Ensure upper entrant is winner of upper last round etc.

        return new_bracket


    def _reorder_ub(self):
        first_round = min(self.ub_rounds)
        last_round = max(self.ub_rounds)
        return self._reorder_rounds(first_round, last_round)


    def _reorder_lb(self):
        first_round = max(self.lb_rounds)
        last_round = min(self.lb_rounds)
        return self._reorder_rounds(first_round, last_round)


    def reorder_sets(self):
        ub = self._reorder_ub()
        lb = self._reorder_lb()
        self.sets = {**ub, **lb}


    def _connect_sets(self):
        # (TODO): For now we just delete unbalanced rounds, as they harder to
        # draw, and usually contain less interesting matches.
        first_ub, first_lb = min(self.ub_rounds), max(self.lb_rounds)
        for round in self.sets.copy():
            if round in [first_ub, first_lb]:
                inc = -1 if round < 0 else 1
                sets_in_round = len(self.sets[round])
                sets_in_next_round = len(self.sets[round+inc])

                if sets_in_round == sets_in_next_round:
                    continue

                if not math.log2(sets_in_round).is_integer() or sets_in_round == 1:
                    del self.sets[round]

        rounds = self.sets.keys()
        ub_rounds = self.ub_rounds
        lb_rounds = self.lb_rounds

        for round in ub_rounds:
            if round == self.last_round:
                gf_sets = self.sets[round]
                if gf_sets[0].is_grand_final and len(gf_sets) > 1:
                    gf_sets[0]._add_parent(gf_sets[1])
                    gf_sets[1]._add_child(gf_sets[0].id, gf_sets[0])

                    self.sets[round] = [gf_sets[0]]
                    self.sets[round+1].append(gf_sets[1])
                else:
                    continue

            for set in self.sets[round]:
                set.connect(self.sets[round+1])

        for round in lb_rounds:
            if round == min(lb_rounds):
                continue

            for set in self.sets[round]:
                set.connect(self.sets[round-1])

        self.reorder_sets()


    def finalize_bracket_tree(self):
        if self.type != BracketType.DOUBLE_ELIMINATION:
            raise ValueError(f'Invalid bracket type {self.type}')

        self._connect_sets()
        sets = deque()
        sets.append(self.grand_final)
        sets.append(self.losers_final)
        while sets:
            set = sets.popleft()
            for child_set in set._children.values():
                sets.append(child_set)
            set.nodify()

        self.upper_bracket = self.grand_final.node
        self.lower_bracket = self.losers_final.node


    def render_bracket_raw(self):
        repr = ''
        repr += 'UPPER BRACKET\n'
        for pre, _, node in RenderTree(self.upper_bracket):
            repr += f'{pre, str(node.name)}\n'
        repr += 'LOWER BRACKET'
        for pre, _, node in RenderTree(self.lower_bracket):
            repr += f'{pre, str(node.name)}\n'
        return repr[:-1]


    def render_bracket(self):
        print(self.render_bracket_raw())


    def render_pool(self):
        raise NotImplementedError(f'Render not implemented for {self.type}')


    def render(self):
        if self.type == BracketType.DOUBLE_ELIMINATION:
            self.render_bracket()
        elif self.type == BracketType.ROUND_ROBIN:
            self.render_pool()
        else:
            raise NotImplementedError(f'Render not implemented for {self.type}')
