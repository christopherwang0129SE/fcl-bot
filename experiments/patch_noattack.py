#!/usr/bin/env python3
"""Turn off all offence, so the game runs its full 1000 rounds and we can see
the bot's economic ceiling with the map to itself."""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")
old = """    def _bot_without_orders(self, ct: Controller) -> None:
        \"\"\"When the builder does not have an order it can do this\"\"\"
        pos = ct.get_position()"""
new = """    def _bot_without_orders(self, ct: Controller) -> None:
        \"\"\"ECONOMY-CEILING PROBE: never attack, just heal and idle.\"\"\"
        pos = ct.get_position()
        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                ct.heal(tile)
                return
        for d in CARDINALS:
            if ct.can_move(d):
                ct.move(d)
                self.moved_direction = d
                return
        return

    def _unused_bot_without_orders(self, ct: Controller) -> None:
        pos = ct.get_position()"""
assert s.count(old) == 1, "anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
