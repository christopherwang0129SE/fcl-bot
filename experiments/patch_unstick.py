#!/usr/bin/env python3
"""Release a build order that has stopped making progress.

README idea: "Smarter pathfinding to avoid getting stuck". BFS already exists;
what's missing is an escape hatch. _execute_buildplan has none: if the next
conveyor tile cannot be built -- route planned through unscouted ground that
turned out to be wall, or something parked on it -- the builder retries the
same blocked tile forever and never clears its order slot. The core keeps that
slot assigned, so the builder is dead weight for the rest of the game AND one
of only three order slots is permanently burned.

Measured in isolation this time; previously it was only ever bundled with other
changes, so its own effect was never visible.
"""
import sys

path = sys.argv[1] + "/main.py"
s = open(path, newline="").read().replace("\r\n", "\n")

old = """    def _execute_buildplan(self, ct: Controller):
        bot_position = ct.get_position()"""
new = """    def _execute_buildplan(self, ct: Controller):
        bot_position = ct.get_position()

        # Watchdog: if none of stage/step/position changes for a while we are
        # wedged. Drop the order so the core can reassign the slot.
        progress = (self.build_stage, self.path_index, bot_position)
        if progress == self.last_progress:
            self.stall += 1
        else:
            self.stall = 0
            self.last_progress = progress
        if self.stall > BUILD_STALL_LIMIT:
            ct.write_store(self.build_order_slot, 0)
            self.build_stage = -1
            self.follow_path = None
            self.stall = 0
            return"""
assert old in s, "execute_buildplan anchor"
s = s.replace(old, new, 1)

s = s.replace("        self.follow_path: Direction|None = None",
              "        self.follow_path: Direction|None = None\n"
              "        self.stall: int = 0\n"
              "        self.last_progress = None", 1)

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "# Turns a builder may hold a build order with no progress at all.\n"
              "BUILD_STALL_LIMIT = 15", 1)

open(path, "w", newline="").write(s)
print(f"patched {path}")
