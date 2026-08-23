#!/usr/bin/env python3
"""Copy the top teams' turret game: forward GUNNERS alongside the sentinels.

Profiling the ladder (experiments/profile_bot.py) shows what the winners field:

  Bean counters (#2, won)  8 gunners, first turn 29, placed 26 tiles forward
  Pivot (#3, won)          4 gunners, first turn 24, 8 tiles forward
  us                       0 gunners, 1-2 sentinels

Our builder only ever builds a SENTINEL, and only on an adjacent tile that bears
on the enemy core. CLAUDE.md measured why that is rare: across 347 siege turns,
131 turns had a buildable adjacent tile and 173 had a bearing tile, but only 5
had the same tile do both. So the siege converts almost nothing.

A gunner is a second, cheaper way to convert the same opportunity: 20 Ti base
against 30, reload 1 against 2, and it only needs line of sight rather than the
sentinel's ignore-obstacles shot. Adding it does not change what a builder wants
to do -- it still marches at the enemy core -- it gives it more chances to spend
a turn on firepower when it gets there.

Variants:
  --targets core      gunner must bear on the enemy core (default)
  --targets any       gunner may bear on any enemy building it can see
  --nofirstheal       do not spend the siege turn healing if a turret is buildable

  python3 patch_hailmary.py <botdir> [--targets core|any] [--nofirstheal]
"""
import sys

d = sys.argv[1]
targets = "core"
if "--targets" in sys.argv:
    targets = sys.argv[sys.argv.index("--targets") + 1]
nofirstheal = "--nofirstheal" in sys.argv

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new, n=1):
    global s
    assert s.count(old) == n, "anchor x%d: %r" % (s.count(old), old.strip()[:60])
    s = s.replace(old, new, n)


# ---- helper: where could a gunner placed here actually shoot from?
sub("""def adjacent_tiles(tile: Position) -> list[Position]:""",
    """def gunner_could_hit_from(tile: Position, targets: list[Position], ct: Controller) -> Direction | None:
    \"\"\"A gunner is the cheap second way to convert a siege tile: 20 Ti against
    the sentinel's 30 and reload 1 against 2. It needs line of sight, so it is
    only worth placing where can_fire_from() already says the shot lands.\"\"\"
    for direction in Direction:
        for target in targets:
            if ct.can_fire_from(tile, direction, EntityType.GUNNER, target):
                return direction
    return None


def enemy_buildings_in_sight(ct: Controller) -> list[Position]:
    out = []
    for bid in ct.get_nearby_buildings():
        try:
            if ct.get_team(bid) != ct.get_team():
                out.append(ct.get_position(bid))
        except GameError:
            continue
    return out


def adjacent_tiles(tile: Position) -> list[Position]:""")

# ---- siege: after the sentinel attempt, try a gunner on the same opportunity
old_siege = """        if self.opp_core_tiles:
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):
                    orientation = sentinel_could_hit_opp_core_from(tile, self.opp_core_tiles, ct)
                    if orientation:
                        ct.build_sentinel(tile, orientation)
                        return
"""
new_siege = """        if self.opp_core_tiles:
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):
                    orientation = sentinel_could_hit_opp_core_from(tile, self.opp_core_tiles, ct)
                    if orientation:
                        ct.build_sentinel(tile, orientation)
                        return
            # The sentinel is unaffordable or no adjacent tile carries its shot.
            # A gunner is cheaper and converts the same opportunity.
            gun_targets = list(self.opp_core_tiles)
            if %r:
                gun_targets = gun_targets + enemy_buildings_in_sight(ct)
            for tile in adjacent_tiles(pos):
                if ct.can_build_gunner(tile, Direction.NORTH):
                    orientation = gunner_could_hit_from(tile, gun_targets, ct)
                    if orientation:
                        ct.build_gunner(tile, orientation)
                        return
""" % (targets == "any",)
sub(old_siege, new_siege)

if nofirstheal:
    # Healing is our most common action (115x/game). While a turret is placeable
    # the turn is better spent on firepower.
    sub("""        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                ct.heal(tile)
                return

        if self.opp_core_tiles:""",
        """        turret_placeable = self.opp_core_tiles and any(
            ct.can_build_sentinel(t, Direction.NORTH) or ct.can_build_gunner(t, Direction.NORTH)
            for t in adjacent_tiles(pos))
        if not turret_placeable:
            for tile in adjacent_tiles(pos):
                if ct.can_heal(tile):
                    ct.heal(tile)
                    return

        if self.opp_core_tiles:""")

open(p, "w", newline="").write(s.replace("\n", nl))
print("patched %s: gunners targeting %s%s" % (d, targets, ", heal deferred" if nofirstheal else ""))
