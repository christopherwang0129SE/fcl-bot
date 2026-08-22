#!/usr/bin/env python3
"""Stop planning new harvesters once the economy is big enough, or late enough.

The live core caps *concurrent* build orders at three but keeps planning new
ones for as long as any unmined ore is known, so in a long game builder-turns
keep draining into mining forever. The literal form of "cap the eco-build so the
builders favour attacking" is therefore a cap on the total number of harvester
orders ever issued, and/or a round after which none are issued at all.

Note what CLAUDE.md already establishes before reading a result here: the
incumbent's three-order economy is *well sized* -- in `bots/econ`, capping belt
runs at 0 scored 16.7% and every phase-switch variant lost -- so the prior is
that a tighter cap costs more than it gains. What has never been tested is a cap
on the *incumbent's* planner rather than on a rewritten one, and the case that
motivates it is the long game, where the incumbent keeps mining for 900 rounds.

  python3 patch_ecocap.py <botdir> [max_orders] [cutoff_round]
"""
import sys

d = sys.argv[1]
max_orders = int(sys.argv[2]) if len(sys.argv) > 2 else 4
cutoff = int(sys.argv[3]) if len(sys.argv) > 3 else 0

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new):
    global s
    assert s.count(old) == 1, "anchor: " + old.strip().split("\n")[0][:60]
    s = s.replace(old, new, 1)


sub("""        self.build_orders_made: list[tuple[Position, int]] = []""",
    """        self.build_orders_made: list[tuple[Position, int]] = []
        self.orders_issued = 0""")

sub("""        for i in range(0,3-len(self.build_orders_made)):
            if not ENV_MAP.unplanned_ore: break
            possible, go_to, build_direction, conveyor_path = ENV_MAP.plan_easiest_harvester()
            if possible:
                build_order_number = encode_build_order(go_to, EntityType.HARVESTER, build_direction,
                                                        conveyor_path)
                self.build_orders_made.append((go_to,build_order_number))""",
    """        economy_open = self.orders_issued < %d
        if %d and ct.get_current_round() >= %d:
            economy_open = False   # past this round every builder-turn is siege
        for i in range(0,3-len(self.build_orders_made)):
            if not ENV_MAP.unplanned_ore: break
            if not economy_open: break
            possible, go_to, build_direction, conveyor_path = ENV_MAP.plan_easiest_harvester()
            if possible:
                build_order_number = encode_build_order(go_to, EntityType.HARVESTER, build_direction,
                                                        conveyor_path)
                self.build_orders_made.append((go_to,build_order_number))
                self.orders_issued += 1
                economy_open = self.orders_issued < %d""" % (max_orders, 1 if cutoff else 0, cutoff or 0, max_orders))

open(p, "w", newline="").write(s.replace("\n", nl))
print("economy cap: %d orders%s -> %s"
      % (max_orders, (", none after round %d" % cutoff) if cutoff else "", d))
