#!/usr/bin/env python3
"""Give a scouter3/scouter4-lineage bot the pathfinding that fixed the stalls.

The scouter4 line searches for a route inside `ct.get_nearby_tiles()` only --
a builder there keeps no map of its own, so every march longer than its vision
radius is a greedy walk with a `lost_at` blacklist bolted on. That is why
`scouter4-patched` goes 0-10 on yulerune and 0-10 on midgard against v8 while
winning 10-0 on drakkarfjord, royale and ragnarok: the economy is ahead and the
builders never arrive.

`scouter2-robust` (v8) solved this and the ladder confirmed it -- longhouse went
from 1-18 to 13-4 once builders kept a local map and planned on it. This ports
that mechanism across the lineage split:

  * each builder builds `local_map` from `get_nearby_tiles()` every turn,
  * `_bot_pathfind` runs a real BFS on it with a `blocked` set of tiles seen to
    hold a building, and caches the route,
  * a step is popped only when the move actually happened (builders move on a
    cooldown, so spending a step on a cooldown round silently discards half a
    long route -- the `longhouse` freeze),
  * `_unstick` records the obstacle, drops the stale route, and sidesteps.

It also closes the two unguarded `get_tile_building_id()` calls the scouter4
line still carries. Off the edge of the map that getter RAISES, and an uncaught
exception destroys the unit permanently for the rest of the match.

  python3 patch_robustpath.py <botdir>
"""
import os, shutil, sys

d = sys.argv[1]
p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new, count=1):
    global s
    assert s.count(old) == count, "anchor x%d: %r" % (s.count(old), old.strip().split("\n")[0][:70])
    s = s.replace(old, new, count)


# ---------------------------------------------------------------- imports
sub("from mapclass import Map, print_conveyor_info",
    "import random\nfrom mapclass import Map, print_conveyor_info\nfrom pathfind import bfs_path")

# ---------------------------------------------------------------- state
sub("""        self.lost_at: set[Position] = set()""",
    """        self.lost_at: set[Position] = set()
        self.local_map: Map | None = None
        self.path: list[Direction] | None = None
        self.current_target: Position | None = None
        self.blocked: dict = {}          # tile -> round it was last seen blocked""")

# ------------------------------------------------- OOB-safe building lookup
sub("""ENV_MAP = Map()""",
    """ENV_MAP = Map()


def building_id_at(tile: Position, ct: Controller):
    \"\"\"get_tile_building_id() raises off the edge of the map, and an uncaught
    exception destroys the unit for the rest of the match. Every can_*() is
    False out of bounds, so only the getters need the guard.\"\"\"
    try:
        return ct.get_tile_building_id(tile)
    except GameError:
        return None""")

sub("""                    blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))""",
    """                    blocked_by_id = building_id_at(bot_position.add(self.build_direction), ct)""", 2)
sub("""                    blocked_by_id = ct.get_tile_building_id(next_tile)""",
    """                    blocked_by_id = building_id_at(next_tile, ct)""")

# ---------------------------------------------------------------- pathfind
old_pathfind = '''    def _bot_pathfind(self, target: Position, ct:Controller) -> None:
        """Moves toward target based on own vision, moves and updates self.moved_direction"""
        visible_tiles = ct.get_nearby_tiles()
        ct.draw_indicator_dot(target, 0,255,255)
        if target not in visible_tiles or target in self.lost_at:
            target = min(visible_tiles, key=lambda tile: tile.distance_squared(target) if (ct.is_tile_passable(tile) and tile not in self.lost_at) else 2047)
        print(f"Pathfind: {target=}")
        if not ct.is_tile_passable(target):
            print(f"Pathfind target is not passable")
            pass # TODO handle this
        suggested_move = self._generate_move_path(target, ct)
        if not suggested_move:
            print("Pathfinding failed")
            self.lost_at.add(target)
            self.lost_at.add(ct.get_position())
            for position in self.lost_at: ct.draw_indicator_dot(position, 0,0,255)
            #print([f"({pos.x},{pos.y})" for pos in self.lost_at])
            options = [tile for tile in adjacent_tiles(ct.get_position()) if ct.can_move(ct.get_position().cardinal_direction_to(tile))]
            print(f"{options=}")
            if options: suggested_move = ct.get_position().cardinal_direction_to(min(options, key=lambda tile: tile.distance_squared(target)))
        else: self.lost_at.clear()
        if suggested_move:
            if ct.can_move(suggested_move):
                ct.move(suggested_move)
                self.moved_direction = suggested_move
'''

new_pathfind = '''    def _note_blocked_tiles(self, ct: Controller) -> None:
        """Record which visible tiles cannot be walked on. Only tiles holding a
        building are remembered: a tile blocked by another builder clears again
        a round later, and treating that as terrain would carve phantom walls
        into the route. Entries expire so a demolished building is forgotten."""
        now = ct.get_current_round()
        for tile in ct.get_nearby_tiles():
            if building_id_at(tile, ct) is not None and not ct.is_tile_passable(tile):
                self.blocked[tile] = now
            elif tile in self.blocked:
                del self.blocked[tile]
        if len(self.blocked) > 60:
            for tile in [t for t, seen in self.blocked.items() if now - seen > 12]:
                del self.blocked[tile]

    def _update_local_map(self, ct: Controller) -> None:
        if self.local_map is None:
            self.local_map = Map()
            self.local_map.configure(ct.get_map_width(), ct.get_map_height(), ct.get_position())
        for tile in ct.get_nearby_tiles():
            self.local_map.set_environment_at(tile, ct.get_tile_env(tile))
        self._note_blocked_tiles(ct)

    def _bot_pathfind(self, target: Position, ct: Controller) -> None:
        """Navigate toward target by BFS over the builder's own map, with a
        greedy cardinal fallback. Vision-limited search cannot plan a march
        longer than the vision radius, which is the whole stall."""
        pos = ct.get_position()
        if self.local_map is None:
            self._update_local_map(ct)

        if target != self.current_target or not self.path:
            self.current_target = target
            self.path = bfs_path(self.local_map, pos, target, max_nodes=500,
                                 blocked=set(self.blocked))

        direction = self.path[0] if self.path else None
        if direction is None and target and target != pos:
            direction = pos.cardinal_direction_to(target)

        if direction and direction != Direction.CENTRE and ct.can_move(direction):
            ct.move(direction)
            self.moved_direction = direction
            if self.path:
                self.path.pop(0)   # only spend a step that was actually taken
            return

        if ct.get_move_cooldown() > 0:
            return                 # not blocked, just not our turn to move

        self._unstick(target, direction, ct)

    def _unstick(self, target: Position, wanted: Direction | None, ct: Controller) -> None:
        """The step we wanted is not walkable. Remember the obstacle, drop the
        stale route, and get round it."""
        pos = ct.get_position()
        if wanted and wanted != Direction.CENTRE:
            self.blocked[pos.add(wanted)] = ct.get_current_round()
        self.path = None
        self.current_target = None

        options = [dr for dr in CARDINALS if ct.can_move(dr)]
        if options:
            here = pos.distance_squared(target) if target else 0
            better = [dr for dr in options if pos.add(dr).distance_squared(target) < here]
            step = random.choice(better or options)
            ct.move(step)
            # Must be the direction actually taken: the scout encoding derives
            # which tiles came into view from it, so a wrong value writes wrong
            # terrain into the map every unit shares.
            self.moved_direction = step
            return

        # Boxed in. Break the cheapest enemy building next to us.
        for dr in CARDINALS:
            tile = pos.add(dr)
            if ct.can_fire(tile):
                bid = building_id_at(tile, ct)
                if bid is not None and ct.get_team(bid) != ct.get_team():
                    ct.fire(tile)
                    return
'''
sub(old_pathfind, new_pathfind)

# --------------------------------------------- keep the local map up to date
sub("""    def _run_builder(self, ct: Controller) -> None:
        self.moved_direction = None
        game_data = parse_game_data(ct)""",
    """    def _run_builder(self, ct: Controller) -> None:
        self.moved_direction = None
        self._update_local_map(ct)
        game_data = parse_game_data(ct)""")

open(p, "w", newline="").write(s.replace("\n", nl))

# pathfind.py must exist next to main.py
src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bots", "scouter2-robust", "pathfind.py")
dst = d + "/pathfind.py"
if not os.path.exists(dst):
    shutil.copyfile(src, dst)
print("patched", d)
