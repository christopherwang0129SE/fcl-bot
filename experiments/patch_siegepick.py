#!/usr/bin/env python3
"""Don't let a besieging builder pick a siege tile it can never stand on.

`_bot_without_orders` takes the *closest* tile from
`tiles_to_attack_core_ct_mode()` and paths at it. That list is built from
geometry alone: a tile the builder has never seen is included whatever is
actually on it, so the nearest candidate is routinely a wall. `bfs_path` treats
WALL as blocked, finds no route, and the greedy fallback walks straight into it.
Nothing notices, so the builder spends the rest of the match pressed against the
same rock.

This is the `build_stage == -1` half of the freeze traced on yulerune -- builder
n4 sat at (6,5) with target (12,5) from round 100 to round 600 -- and
`patch_giveup` does not cover it, because that builder has no order to give up.

Fix: skip candidates already known to be WALL, and if the builder has been
rattling around the same couple of tiles for N rounds, blacklist the tile it is
aiming at and take the next one.

  python3 patch_siegepick.py <botdir> [stuck_rounds]
"""
import sys

d = sys.argv[1]
stuck_rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 20

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new):
    global s
    assert s.count(old) == 1, "anchor: " + old.strip().split("\n")[0][:60]
    s = s.replace(old, new, 1)


sub("""        self.current_target: Position | None = None""",
    """        self.current_target: Position | None = None
        self.dead_targets: set = set()
        self.siege_marks: list = []""")

sub("""            attack_tiles = tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)
            if attack_tiles:
                best_tile = min(attack_tiles, key=lambda tile: tile.distance_squared(pos))
                self._bot_pathfind(best_tile, ct)""",
    """            if self._siege_going_nowhere(ct) and self.current_target is not None:
                self.dead_targets.add(self.current_target)
                self.path = None
                self.current_target = None
                self.siege_marks = []

            attack_tiles = [tile for tile in tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)
                            if tile not in self.dead_targets
                            and self.local_map.get_environment_at(tile) != Environment.WALL]
            if attack_tiles:
                best_tile = min(attack_tiles, key=lambda tile: tile.distance_squared(pos))
                self._bot_pathfind(best_tile, ct)""")

sub("""    def _report_to_store(self, ct: Controller) -> None:""",
    '''    def _siege_going_nowhere(self, ct: Controller) -> bool:
        """True once the builder has spent a %d-round window inside two or three
        tiles while trying to reach a siege position. Counts distinct tiles
        rather than demanding an identical one, because a builder wedged against
        an obstacle oscillates -- its cached route is one step out of step with
        where it actually is."""
        self.siege_marks.append(ct.get_position())
        if len(self.siege_marks) > %d:
            self.siege_marks.pop(0)
        return len(self.siege_marks) >= %d and len(set(self.siege_marks)) <= 3

    def _report_to_store(self, ct: Controller) -> None:''' % (stuck_rounds, stuck_rounds, stuck_rounds))

open(p, "w", newline="").write(s.replace("\n", nl))
print("siege target picking (stuck after %d rounds) -> %s" % (stuck_rounds, d))
