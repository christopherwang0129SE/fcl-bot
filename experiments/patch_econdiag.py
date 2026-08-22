#!/usr/bin/env python3
"""Dump each builder's economy state every N rounds (bots/econ only).

Answers gate-1 follow-ups: is the planner running out of *known* ore, out of
*reachable* ore, or losing to claims/blocklists?

Emits: DIAG <team> <round> b<n> net=<..> ore=<..> occ=<..> skip=<..> plan=<..> belts=<..> stall=<..>
"""
import sys

d = sys.argv[1]
p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\nimport sys as _sys\nDIAG_EVERY = 20\n", 1)

old = """        self._publish_report(ct)
        if self.scout_store_slot > 0: self._report_to_store(ct)"""
new = """        if ct.get_current_round() % DIAG_EVERY == 0:
            print('DIAG %s %d b%d net=%d ore=%d occ=%d skip=%d blk=%d plan=%s belts=%s stall=%d pos=%s' % (
                ct.get_team(), ct.get_current_round(), self.am_builder_number,
                len(self.net), len(self.local_map.unplanned_ore), len(self.occupied_ore),
                len(self.skip_ore), len(self.blocked),
                self.plan.ore if self.plan else None,
                len(self.plan.belts) if self.plan else -1,
                self.stall, ct.get_position()), file=_sys.stderr)

        self._publish_report(ct)
        if self.scout_store_slot > 0: self._report_to_store(ct)"""
assert s.count(old) == 1
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s.replace("\n", nl))
print("diag patched " + d)
