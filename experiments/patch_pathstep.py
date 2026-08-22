#!/usr/bin/env python3
"""Stop discarding path steps the builder never actually took.

_bot_pathfind caches a BFS route and pops the next direction off it every call,
whether or not the move happened. Builder bots move on a cooldown, so on every
cooldown turn a step was thrown away and the remainder of the route pointed at
tiles the builder had never reached. Found while rewriting the economy: one
builder sat on the same tile from turn 20 to turn 83 because of it.

This is independent of the economy work -- it costs the incumbent movement on
its cross-map siege march too, which is the thing the whole bot is built on.

  python3 patch_pathstep.py <botdir>
"""
import sys

p = sys.argv[1] + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = """        # Follow the path if we have one
        direction = None
        if self.path:
            direction = self.path.pop(0)

        # Fallback: greedy cardinal step if no path found
        if direction is None and target and target != pos:
            direction = pos.cardinal_direction_to(target)

        # Try to move
        if direction and direction != Direction.CENTRE and ct.can_move(direction):
            ct.move(direction)
            self.moved_direction = direction"""
new = """        # Follow the path if we have one. Peek, do not pop: the step is only
        # spent if the move actually happens.
        direction = self.path[0] if self.path else None

        # Fallback: greedy cardinal step if no path found
        if direction is None and target and target != pos:
            direction = pos.cardinal_direction_to(target)

        # Try to move
        if direction and direction != Direction.CENTRE:
            if ct.can_move(direction):
                ct.move(direction)
                self.moved_direction = direction
                if self.path and self.path[0] == direction:
                    self.path.pop(0)
            elif ct.get_move_cooldown() == 0:
                self.path = None    # not cooldown, so genuinely blocked -- reroute"""
assert s.count(old) == 1, "pathfind anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s.replace("\n", nl))
print("patched " + sys.argv[1])
