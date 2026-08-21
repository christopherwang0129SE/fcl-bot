#!/usr/bin/env python3
"""Late builder cull: shed the order-less builder once its work is done.

User's idea, in the form the evidence can support. Cost scale is a STOCK, not a
spend -- destroying an entity removes its +20% contribution -- and nothing in
this bot exploits that. The version that failed on paper was boom-then-bust
(many miners early, cull later): it pays the inflated price precisely while
buying the economy, and has to transit the 5-6 builder regime (30.7% / 22.7%)
to reach the 2-3 regime (38.7% / 44.0%).

So: hold the measured optimum of 4 builders through the whole economy phase, and
only late -- once the map is developed and this builder has no build order left
to run -- have the surplus builder self-destruct. That converts a unit which is
mostly wandering into a permanent 20% discount on every remaining sentinel,
harvester and belt, at the moment we most want to buy turrets.

Only builder 4+ culls: builders 1-3 own the build-order slots, so culling them
would strand mining work.
"""
import sys
r = int(sys.argv[2])
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              f"SLOT_GAME_DATA = 0\n\n"
              f"# Round after which a surplus (order-less) builder trades itself for the\n"
              f"# +20% cost scale it is holding. Builders 1-3 own order slots and stay.\n"
              f"CULL_ROUND = {r}\n"
              f"FIRST_CULLABLE_BUILDER = 4", 1)

old = """    def _bot_without_orders(self, ct: Controller) -> None:
        \"\"\"When the builder does not have an order it can do this\"\"\"
        pos = ct.get_position()"""
new = """    def _bot_without_orders(self, ct: Controller) -> None:
        \"\"\"When the builder does not have an order it can do this\"\"\"
        pos = ct.get_position()

        # Surplus builder, late game: our +20% cost scale is worth more to the
        # team as a discount on turrets than this unit is as another wanderer.
        if (self.am_builder_number >= FIRST_CULLABLE_BUILDER
                and ct.get_current_round() >= CULL_ROUND):
            ct.self_destruct()
            return"""
assert s.count(old) == 1, "bot_without_orders anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p} -> cull builder>={4} after round {r}")
