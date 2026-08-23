#!/usr/bin/env python3
"""Use the LAUNCHER as a catapult for our own builders.

Our bot implements CORE, BUILDER_BOT and SENTINEL only -- the launcher has never
been given any code. CLAUDE.md rules launchers out, but only for the *defensive*
use (throwing enemy builders away from our core, which needs enemy builders to
appear there and they mostly do not). The offensive use is untouched, and it
attacks the one bottleneck this session actually measured:

    our median first sentinel   turn 34
    a real opponent's           turn 8-12
    builder movement            ~0.85 tiles/turn, identical for both sides
    the midgard trace           38 tiles walked in 40 turns, straight line

The march is geometry. A launcher is the only thing in the API that changes the
geometry: it picks up an adjacent builder bot -- from either team -- and throws
it to a passable tile within r^2=26, about 5.1 tiles, on a fire cooldown of 1.
That is roughly six turns of walking, bought for 20 Ti and +10% cost scale,
which is half what a turret adds.

So a marching builder leapfrogs: spend one turn building a launcher behind it,
get thrown ~5 tiles forward on the launcher's next turn, repeat. Capped, because
each launcher is +10% scale forever and the siege is money-limited.

  python3 patch_catapult.py <botdir> [max_launchers]
"""
import sys

d = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 3

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new, n=1):
    global s
    assert s.count(old) == n, "anchor x%d: %r" % (s.count(old), old.strip()[:60])
    s = s.replace(old, new, n)


sub("""        self.blocked: dict = {}          # tile -> round it was last seen blocked""",
    """        self.blocked: dict = {}          # tile -> round it was last seen blocked
        self.launchers_built = 0
        self.last_launch_build = -99""")

# ---- dispatch: give the launcher a brain
sub("""        elif etype == EntityType.SENTINEL:
            self._run_sentinel(ct)""",
    """        elif etype == EntityType.SENTINEL:
            self._run_sentinel(ct)

        elif etype == EntityType.LAUNCHER:
            self._run_launcher(ct)""")

# ---- the launcher itself
sub("""    def _run_sentinel(self, ct: Controller) -> None:""",
    """    def _run_launcher(self, ct: Controller) -> None:
        \"\"\"Throw a friendly builder as far toward the enemy core as the arc
        reaches. A launch is free of the builder's own action and move cooldown,
        so it is strictly faster than the walk it replaces.\"\"\"
        if not self.opp_core_tiles:
            return
        goal = self.opp_core_tiles[0]
        here = ct.get_position()
        for tile in adjacent_tiles(here):
            bot_id = None
            try:
                bot_id = ct.get_tile_builder_bot_id(tile)
            except GameError:
                continue
            if not bot_id or ct.get_team(bot_id) != ct.get_team():
                continue
            gain = tile.distance_squared(goal)
            best, best_d = None, gain
            for dest in ct.get_nearby_tiles():
                if dest.distance_squared(goal) >= best_d:
                    continue
                if not ct.is_tile_passable(dest):
                    continue
                if ct.can_launch(tile, dest):
                    best, best_d = dest, dest.distance_squared(goal)
            if best is not None:
                ct.launch(tile, best)
                return

    def _run_sentinel(self, ct: Controller) -> None:""")

# ---- the marching builder lays a catapult behind itself
sub("""            attack_tiles = [tile for tile in tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)""",
    """            # Leapfrog: one turn spent building a launcher behind us buys ~5
            # tiles on its next turn, against ~0.85 tiles/turn on foot.
            if (self.launchers_built < %d
                    and ct.get_current_round() - self.last_launch_build > 3
                    and pos.distance_squared(self.opp_core_tiles[0]) > 64):
                ahead = min(adjacent_tiles(pos), key=lambda t: t.distance_squared(self.opp_core_tiles[0]))
                if ct.can_build_launcher(ahead):
                    ct.build_launcher(ahead)
                    self.launchers_built += 1
                    self.last_launch_build = ct.get_current_round()
                    return

            # A launch only happens while we are still standing next to the
            # launcher, so hold position for the turn after building one.
            if 0 <= ct.get_current_round() - self.last_launch_build <= 2:
                for t in adjacent_tiles(pos):
                    bid = building_id_at(t, ct)
                    if bid and ct.get_team(bid) == ct.get_team() \
                            and ct.get_entity_type(bid) == EntityType.LAUNCHER:
                        return          # wait to be thrown

            attack_tiles = [tile for tile in tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)""" % cap)

open(p, "w", newline="").write(s.replace("\n", nl))
print("patched %s: catapult, max %d launchers" % (d, cap))
