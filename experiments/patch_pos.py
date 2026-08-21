#!/usr/bin/env python3
"""Stop recording every builder as standing on the map origin.

A builder that did not move writes 0 to its scout slot, which decodes to
Position(0, 0), and the core stores that as the builder's location -- so in a
long game all three read as (0,0) forever. Combined with the dist=63 assignment
radius that means the core will only ever hand out ore within ~8 tiles of the
map corner, and the harvester count freezes.

Fixing this ALONE measured 43.3%, because in an 85-turn rush game mining is not
what wins. It belongs with the turtle, where games reach round 1000.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")
old = """            self.builder_positions[i] = read_stored_scout(scout_slot, ENV_MAP, ct)"""
new = """            reported = read_stored_scout(scout_slot, ENV_MAP, ct)
            # 0 means "did not move", which decodes to (0,0); keep the last real fix.
            if reported != Position(0, 0):
                self.builder_positions[i] = reported"""
assert s.count(old) == 1, "scout anchor"
open(p, "w", newline="").write(s.replace(old, new, 1))
print(f"patched {p}")
