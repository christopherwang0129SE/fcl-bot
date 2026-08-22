#!/usr/bin/env python3
"""Make a builder that is blocked do something other than stand still.

Three separate holes, all on the same path:

1. `bfs_path` only treats Environment.WALL as impassable. Buildings are
   invisible to it, so a barrier line, a turret or our own core is routed
   straight through. (Conveyors really are passable -- that is how the
   belt-laying loop works -- so "is there a building" is the wrong test and
   `is_tile_passable` is the right one.)
2. When the chosen step turns out to be unwalkable, `_bot_pathfind` simply
   does not move. It does not replan, does not try another direction, and the
   next round it recomputes the same route to the same wall. A heavily walled
   opponent freezes the siege for the rest of the game.
3. The step is popped off the cached route whether or not the move happened,
   so every blocked or cooldown round silently desyncs the rest of the route
   from where the builder actually is.

The fix keeps a small decaying set of tiles known to be unwalkable, feeds it to
BFS, only consumes a step when the move succeeds, and -- when there is no route
at all -- sidesteps toward the target, and failing that attacks the enemy
building in the way. Breaking through is the last resort, not the first: it
costs the action cooldown, which CLAUDE.md records as the reason raiding lost.

  python3 patch_blocked.py <botdir> [forget_after]
"""
import sys

d = sys.argv[1]
forget_after = int(sys.argv[2]) if len(sys.argv) > 2 else 12

# --------------------------------------------------------------- pathfind --
p = d + "/pathfind.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")

old = "def bfs_path(map_obj: Map, start: Position, goal: Position, max_nodes: int = 1000) -> list[Direction] | None:"
new = "def bfs_path(map_obj: Map, start: Position, goal: Position, max_nodes: int = 1000, blocked: set | None = None) -> list[Direction] | None:"
assert s.count(old) == 1, "bfs signature"
s = s.replace(old, new, 1)

old = """            env = map_obj.environment_grid[next_pos.y][next_pos.x]
            if env == Environment.WALL:
                continue"""
new = """            env = map_obj.environment_grid[next_pos.y][next_pos.x]
            if env == Environment.WALL:
                continue
            # Tiles seen to be unwalkable -- buildings, the enemy core, a wall
            # of barriers -- are not in the environment grid at all.
            if blocked and next_pos in blocked and next_pos != goal:
                continue"""
assert s.count(old) == 1, "bfs wall test"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s.replace("\n", nl))

# ------------------------------------------------------------------- main --
p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new, count=1):
    global s
    assert s.count(old) == count, "anchor: " + old.strip().split("\n")[0][:60]
    s = s.replace(old, new)


sub("""        self.current_target: Position | None = None
        self.path: list[Direction] | None = None""",
    """        self.current_target: Position | None = None
        self.path: list[Direction] | None = None
        self.blocked: dict = {}          # tile -> round it was last seen blocked""")

sub("""    def _bot_pathfind(self, target: Position, ct: Controller) -> None:
        \"\"\"Navigate toward target using BFS pathfinding with greedy fallback.\"\"\"
        pos = ct.get_position()

        # If target changed, recompute path via BFS
        if target != self.current_target or not self.path:
            self.current_target = target
            self.path = bfs_path(self.local_map, pos, target, max_nodes=500)

        # Follow the path if we have one
        direction = None
        if self.path:
            direction = self.path.pop(0)

        # Fallback: greedy cardinal step if no path found
        if direction is None and target and target != pos:
            direction = pos.cardinal_direction_to(target)

        # Try to move
        if direction and direction != Direction.CENTRE and ct.can_move(direction):
            ct.move(direction)
            self.moved_direction = direction""",
    """    def _note_blocked_tiles(self, ct: Controller) -> None:
        \"\"\"Record which visible tiles cannot be walked on. Only tiles holding a
        building are remembered: a tile blocked by another builder clears again
        a round later, and treating that as terrain would carve phantom walls
        into the route. Entries expire so a demolished building is forgotten.\"\"\"
        now = ct.get_current_round()
        for tile in ct.get_nearby_tiles():
            if ct.get_tile_building_id(tile) is not None and not ct.is_tile_passable(tile):
                self.blocked[tile] = now
            elif tile in self.blocked:
                del self.blocked[tile]
        if len(self.blocked) > 60:
            for tile in [t for t, seen in self.blocked.items() if now - seen > %d]:
                del self.blocked[tile]

    def _bot_pathfind(self, target: Position, ct: Controller) -> None:
        \"\"\"Navigate toward target using BFS pathfinding with greedy fallback.\"\"\"
        pos = ct.get_position()

        # If target changed, recompute path via BFS
        if target != self.current_target or not self.path:
            self.current_target = target
            self.path = bfs_path(self.local_map, pos, target, max_nodes=500,
                                 blocked=set(self.blocked))

        # Follow the path if we have one
        direction = None
        if self.path:
            direction = self.path[0]

        # Fallback: greedy cardinal step if no path found
        if direction is None and target and target != pos:
            direction = pos.cardinal_direction_to(target)

        # Try to move
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
        \"\"\"The step we wanted is not walkable. Remember the obstacle, drop the
        stale route, and get round it.\"\"\"
        pos = ct.get_position()
        if wanted and wanted != Direction.CENTRE:
            self.blocked[pos.add(wanted)] = ct.get_current_round()
        self.path = None
        self.current_target = None

        options = [dr for dr in CARDINALS if ct.can_move(dr)]
        if options:
            # Prefer a sidestep that does not lose ground on the target.
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
                bid = ct.get_tile_building_id(tile)
                if bid is not None and ct.get_team(bid) != ct.get_team():
                    ct.fire(tile)
                    return""" % forget_after)

sub("""        for tile in ct.get_nearby_tiles():
            env = ct.get_tile_env(tile)
            self.local_map.set_environment_at(tile, env)""",
    """        for tile in ct.get_nearby_tiles():
            env = ct.get_tile_env(tile)
            self.local_map.set_environment_at(tile, env)
        self._note_blocked_tiles(ct)""")

open(p, "w", newline="").write(s.replace("\n", nl))
print("blocked-tile pathfinding (forget after %d) -> %s" % (forget_after, d))
