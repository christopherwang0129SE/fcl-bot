#!/usr/bin/env python3
"""Always commit to a map symmetry, so the bot always has a core to attack.

discover_symmetry() only accepts a symmetry when exactly ONE candidate survives
its tests. On maps where two remain consistent -- which happens whenever
scouting stalls before the map is distinguishable -- it never commits, the
opponent core is never deduced, and _bot_without_orders falls through to
"wander toward the opposite corner" for the rest of the match.

Measured against an opponent that does NOTHING: on yulerune symmetry is still
None at round 1000, the bot builds zero sentinels all game and only wins on the
titanium tiebreak (real ladder record there: 1-6). On longhouse (0-13) the
first sentinel lands on turn 366 of a 385-turn game. A mirror A/B is blind to
all of this -- both sides are equally lost, so it reads ~50%.

Committing is not enough on its own: on yulerune both rotational and horizontal
survive, and guessing rotational marches everyone to an empty corner. So a
candidate whose predicted core site we have already scouted and found bare is
skipped -- their core cannot be somewhere we have looked and seen nothing.

  python3 patch_symcommit.py <botdir> [commit_round]
"""
import sys

d = sys.argv[1]
commit_round = int(sys.argv[2]) if len(sys.argv) > 2 else 40

NEW_BODY = '''    def discover_symmetry(self, force: bool = False) -> bool:
        possible = []
        for symmetry_kind in [SYMMETRY_ROTATIONAL, SYMMETRY_HORIZONTAL, SYMMETRY_VERTICAL]:
            if self.test_for_symmetry_kind(symmetry_kind) and self.test_for_symmetry_by_cores(symmetry_kind):
                possible.append(symmetry_kind)
        if len(possible) == 1:
            self.known_symmetry = possible[0]
            return True
        if force and possible:
            # Still ambiguous, and waiting has not been working: commit anyway.
            # Being wrong costs a walk in the wrong direction; never committing
            # costs the whole game. Skip any candidate whose predicted core site
            # we have already scouted and found bare.
            for kind in possible:
                if not self._core_site_refuted(kind):
                    self.known_symmetry = kind
                    return True
            self.known_symmetry = possible[0]
            return True
        return False

    def _mirror_of(self, tile: Position, symmetry_kind: int) -> Position:
        if symmetry_kind == SYMMETRY_HORIZONTAL:
            return Position(self.width - tile.x - 1, tile.y)
        if symmetry_kind == SYMMETRY_VERTICAL:
            return Position(tile.x, self.height - tile.y - 1)
        return Position(self.width - tile.x - 1, self.height - tile.y - 1)

    def get_entity_at(self, pos: Position) -> int:
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height:
            return 0
        return self.entity_grid[pos.y][pos.x]

    def _core_site_refuted(self, symmetry_kind: int) -> bool:
        # True when we have scouted where this symmetry puts their core and
        # found plain terrain with nothing standing on it.
        for tile in self.own_core:
            guess = self._mirror_of(tile, symmetry_kind)
            if self.get_environment_at(guess) and self.get_entity_at(guess) == 0:
                return True
        return False'''

p = d + "/mapclass.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = """    def discover_symmetry(self) -> bool:
        possible = []
        for symmetry_kind in [SYMMETRY_ROTATIONAL, SYMMETRY_HORIZONTAL, SYMMETRY_VERTICAL]:
            if self.test_for_symmetry_kind(symmetry_kind) and self.test_for_symmetry_by_cores(symmetry_kind):
                possible.append(symmetry_kind)
        if len(possible) == 1:
            self.known_symmetry = possible[0]
            return True
        return False"""
assert s.count(old) == 1, "discover_symmetry anchor"
s = s.replace(old, NEW_BODY, 1)
open(p, "w", newline="").write(s.replace("\n", nl))

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")
old = """        if ENV_MAP.known_symmetry is None:
            if ENV_MAP.discover_symmetry():"""
new = """        if ENV_MAP.known_symmetry is None:
            if ENV_MAP.discover_symmetry(force=ct.get_current_round() >= %d):""" % commit_round
assert s.count(old) == 1, "core symmetry anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s.replace("\n", nl))
print("symmetry commit at round %d -> %s" % (commit_round, d))
