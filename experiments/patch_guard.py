#!/usr/bin/env python3
"""Never let an exception escape run().

Docs: "if run() raises anything besides that timeout, the engine prints the
traceback and permanently destroys that unit -- it will never run again for the
rest of the match." For the core that is effectively losing the game.

No guard exists today. One bad edge case (an empty min(), an IndexError on a
core-tile list, a GameError from an action whose can_*() we forgot) silently
removes a unit for good. Cheap insurance that cannot cost us anything.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

old = """    def run(self, ct: Controller) -> None:

        if self.opp_core_bottom_right is None:"""
new = """    def run(self, ct: Controller) -> None:
        # An exception escaping run() permanently destroys this unit, so never
        # let one out: a bad turn is survivable, losing the unit is not.
        try:
            self._run(ct)
        except Exception:
            pass

    def _run(self, ct: Controller) -> None:

        if self.opp_core_bottom_right is None:"""
assert s.count(old) == 1, "run anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
