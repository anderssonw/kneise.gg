from anytree import Node, RenderTree
from collections import defaultdict, deque


class Set(object):
    def __init__(self, id, phase, round, score, winner_id, entrants):
        self.id = id
        self.phase = phase
        self.round = round
        self.score = score
        self.winner_id = winner_id
        self.entrants = entrants

        self._parent = None
        self._children = {}
        self.node = None


    def __str__(self):
        return f'Set ended: {self.score}'


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
    def __init__(self, id, name=''):
        self.id = id
        self.name = name
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
                repr += f'  \tSet ended: {set.score}\n'
        return repr[:-1]


    @property
    def num_sets(self):
        return sum(len(round) for round in self.sets.values())


    @property
    def last_round(self):
        return max(self.sets.keys())


    @property
    def grand_final(self):
        with_reset_index = len(self.sets[self.last_round])-1
        return self.sets[self.last_round][with_reset_index]


    @property
    def losers_final(self):
        return self.sets[min(self.sets.keys())+1][0]


    def add_set(self, id, phase, round, score, winner_id, entrants):
        set = Set(id, phase, round, score, winner_id, entrants)
        self.sets[round].append(set)


    def _connect_sets(self):
        rounds = self.sets.keys()
        ub_rounds = [round for round in rounds if round > 0]
        lb_rounds = [round for round in rounds if round < 0]

        for round in ub_rounds:
            if round == self.last_round:
                gf_sets = self.sets[round]
                if len(gf_sets) > 1:
                    gf_sets[0]._add_parent(gf_sets[1])
                    gf_sets[1]._add_child(gf_sets[0].id, gf_sets[0])
                continue

            for set in self.sets[round]:
                set.connect(self.sets[round+1])

        for round in lb_rounds:
            for set in self.sets[round]:
                set.connect(self.sets[round-1])


    def finalize_bracket_tree(self):
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


    def render_bracket(self):
        print('UPPER BRACKET')
        for pre, _, node in RenderTree(self.upper_bracket):
            print(f'{pre, str(node.name)}')
        print('LOWER BRACKET')
        for pre, _, node in RenderTree(self.lower_bracket):
            print(f'{pre, str(node.name)}')
