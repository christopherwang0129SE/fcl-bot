#!/usr/bin/env python3
"""Copy the archetype that actually beats us: one builder, one harvester, all sentinels.

Replay forensics on Ouroboros (#33, swept us 0-5) and 'not adgato' (#1) show the
same shape in every game, from two independent teams:

    builders 1     conveyors 0     harvesters 1 (beside their own core, turn 3)
    sentinels 4, planted 18-22 tiles out, on our core

while we field 4-6 builders, 15-20 conveyors and manage 1-2 sentinels.

The mechanism is cost scale, which CLAUDE.md already identifies as the dominant
term: builders are +20% each. At one builder their scale sits near 120%, so four
sentinels cost about 36+42+48+54 = 180 Ti -- comfortably inside the starting 500.
At our 4-6 builders plus belts the scale is 230-260%, each sentinel costs 69-78,
and the siege is money-limited exactly as CLAUDE.md measured.

Note the builder sweep in CLAUDE.md (2 -> 38.7%, 3 -> 44.0%, 4 -> baseline,
5 -> 30.7%) never tested ONE, and was run with the economy architecture intact so
builders were needed to execute build orders. With the economy cut to a single
harvester the trade is completely different. Note also that the naive version of
this -- 4 builders and no economy, experiments/rusher -- loses 150-0, so the low
builder count is the load-bearing half, not the missing economy.

  python3 patch_minimal.py <botdir> [n_builders] [n_harvester_orders]
"""
import sys

d = sys.argv[1]
nb = int(sys.argv[2]) if len(sys.argv) > 2 else 1
nh = int(sys.argv[3]) if len(sys.argv) > 3 else 1

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new, n=1):
    global s
    assert s.count(old) == n, "anchor x%d: %r" % (s.count(old), old[:60])
    s = s.replace(old, new, n)


# the spawn gate, and the damage-response builders on top of it
sub("        if self.bots_made < 4:", "        if self.bots_made < %d:" % nb)
sub("if ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:",
    "if ct.get_hp() < ct.get_max_hp() and self.bots_made < %d:" % (nb + 2))
# order-slot bookkeeping is keyed off the builder count; keep it consistent
sub("        if self.bots_made >= 4:", "        if self.bots_made >= %d:" % nb)
# economy: a single harvester, which is what they build beside their own core
sub("self.orders_issued < 5", "self.orders_issued < %d" % nh, 2)

open(p, "w", newline="").write(s.replace("\n", nl))
print("patched %s: %d builder(s), %d harvester order(s)" % (d, nb, nh))
