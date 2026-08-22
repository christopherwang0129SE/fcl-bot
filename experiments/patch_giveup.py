#!/usr/bin/env python3
"""Abandon a build order the builder cannot actually complete, and go attack.

Measured on yulerune against a do-nothing opponent: three of four builders sit
in `build_stage == 0` from round 100 to round 600+, each oscillating between two
tiles, each holding a build order whose `go_to` it never reaches. The map stops
being scouted at round 100 and the game runs to the round-1000 tiebreak. The
median game on that map is 1000 turns and 8 of 12 never end at all -- and the
real ladder record on the same family of maps is 0-13 (longhouse), 1-6
(yulerune).

There are two ways to fix a builder stuck on an unreachable order: make it
reach the order, or make it drop the order. CLAUDE.md is unambiguous that the
second is the one that wins -- "any use of a builder's action other than walk at
the enemy core and place a sentinel loses" -- and the first turns a frozen
builder into a miner, which is the behaviour ~20 measured variants punished.
So: if a builder has neither moved nor advanced its build stage for N rounds,
it drops the order, frees the store slot, and falls through to the siege.

This is also the natural form of "cap the economy": the cap is not a count of
harvesters, it is a refusal to spend unbounded builder-turns on one that is not
happening.

  python3 patch_giveup.py <botdir> [stuck_rounds]
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


sub("""        self.follow_path: Direction|None = None""",
    """        self.follow_path: Direction|None = None
        self.recent_marks: list = []
        self.abandoned: list = []""")

sub("""        if self.build_stage >= 0:
            self._execute_buildplan(ct)
        else:
            self._bot_without_orders(ct)""",
    """        if self.build_stage >= 0 and self._order_is_going_nowhere(ct):
            self._abandon_order(ct)

        if self.build_stage >= 0:
            self._execute_buildplan(ct)
        else:
            self._bot_without_orders(ct)""")

sub("""    def _report_to_store(self, ct: Controller) -> None:""",
    '''    def _order_is_going_nowhere(self, ct: Controller) -> bool:
        """True once this builder has spent a %d-round window rattling around
        the same two or three tiles without its build stage advancing.

        The first version of this test asked for the position to be *identical*
        each round and caught almost nothing: a stuck builder does not stand
        still, it oscillates, because the cached route is one step out of sync
        with where it actually is. Counting distinct tiles over a window catches
        that, and does not fire on the legitimate slow cases -- a belt run walks
        a new tile every couple of rounds, and a long march changes tile
        constantly even though the stage does not."""
        self.recent_marks.append((ct.get_position(), self.build_stage))
        if len(self.recent_marks) > %d:
            self.recent_marks.pop(0)
        if len(self.recent_marks) < %d:
            return False
        stages = {m[1] for m in self.recent_marks}
        tiles = {m[0] for m in self.recent_marks}
        return len(stages) == 1 and len(tiles) <= 3

    def _abandon_order(self, ct: Controller) -> None:
        """Drop the order and hand the slot back. The core keeps no record of
        an issued ticket, so it will not be re-offered; this builder simply
        rejoins the siege, which is what it is worth more doing anyway."""
        if self.go_to is not None:
            self.abandoned.append(self.go_to)
        if self.build_order_slot > 0:
            ct.write_store(self.build_order_slot, 0)
        self.build_stage = -1
        self.path_index = 0
        self.conveyor_path = []
        self.follow_path = None
        self.path = None
        self.current_target = None
        self.recent_marks = []

    def _report_to_store(self, ct: Controller) -> None:''' % (stuck_rounds, stuck_rounds, stuck_rounds))

open(p, "w", newline="").write(s.replace("\n", nl))
print("give up on a stuck order after %d rounds -> %s" % (stuck_rounds, d))
