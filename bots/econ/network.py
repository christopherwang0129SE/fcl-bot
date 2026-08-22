"""Local, per-builder planning of a contiguous conveyor network.

The old architecture had the core plan one harvester at a time and hand each
builder a fully-encoded ticket (go_to + a packed belt route). That capped us at
three harvesters under construction, and every ticket routed its own private
chain back to the core, so we paid 3-4 belts per harvester.

Here every builder plans for itself out of what it can see. The whole thing
rests on one invariant: *a belt is only ever built adjacent to a tile already
known to be connected to the core*. Given that, "connected" is decidable
locally -- the core tiles are connected, anything we built is connected, and
any friendly belt we see (or hear about over the store) was built under the
same rule, so it is connected too. No central bookkeeping and no ticket
encoding is needed.

Growth is therefore contiguous: the search below starts from *every* network
tile at once, so the next ore is reached by branching off the nearest existing
belt rather than by running a fresh chain home.

Everything inside the search runs on plain (x, y) tuples and raw grid indexing
rather than Position objects. Each unit only gets 10ms per turn, and building a
few thousand NamedTuples per BFS was most of that budget.
"""
from collections import deque

from fcode import Environment, Direction, Position

CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]


def adjacent_tiles(tile: Position) -> list[Position]:
    return [tile.add(direction) for direction in CARDINALS]


class Plan:
    """The next chunk of work for one builder.

    `belts` is the run of tiles still to be laid, ordered outward from the
    network; `anchor` is the connected tile the next belt hooks onto, which is
    also the direction that belt must face so titanium flows toward the core.
    """

    __slots__ = ("ore", "belts", "anchor")

    def __init__(self, ore: Position, belts: list[Position], anchor: Position):
        self.ore = ore
        self.belts = belts
        self.anchor = anchor


def plan_extension(local_map, net: set, ore_tiles, occupied: set, blocked: set,
                   from_pos: Position, skip: set, claimed: set,
                   max_belts: int = 12, max_walk: int | None = None) -> Plan | None:
    """Cheapest way to hook one more ore tile onto the existing network.

    Multi-source BFS outward from `net`. Unscouted tiles are routed through
    optimistically: belts get laid one at a time from an adjacent tile, so the
    builder always sees a tile before building on it, and a route that turns out
    to hit a wall costs one replan rather than any titanium. Refusing to plan
    through unscouted ground instead confined the network to the patch of map
    the builder happened to have walked already. Ore tiles are never routed
    through -- they are destinations, and a belt on one squats a harvester site.
    """
    grid = local_map.environment_grid
    width, height = local_map.width, local_map.height
    wall, ore_env = Environment.WALL, Environment.ORE_TITANIUM

    dist: dict[tuple, int] = {}
    parent: dict[tuple, tuple] = {}
    queue = deque()
    for tile in net:
        x, y = tile.x, tile.y
        if 0 <= x < width and 0 <= y < height and (x, y) not in dist:
            dist[(x, y)] = 0
            queue.append((x, y))
    if not queue:
        return None

    solid = set()
    for tile in blocked:
        solid.add((tile.x, tile.y))

    popleft, append = queue.popleft, queue.append
    while queue:
        cx, cy = popleft()
        step = dist[(cx, cy)] + 1
        if step > max_belts:
            continue
        for nxt in ((cx, cy - 1), (cx, cy + 1), (cx + 1, cy), (cx - 1, cy)):
            nx, ny = nxt
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            if nxt in dist or nxt in solid:
                continue
            env = grid[ny][nx]
            if env == wall or env == ore_env:
                continue
            dist[nxt] = step
            parent[nxt] = (cx, cy)
            append(nxt)

    fx, fy = from_pos.x, from_pos.y
    best_key = None
    best_ore = None
    best_hookup = None
    for ore in ore_tiles:
        if ore in occupied or ore in skip or ore in claimed:
            continue
        ox, oy = ore.x, ore.y
        hookup = None
        best_d = None
        for nxt in ((ox, oy - 1), (ox, oy + 1), (ox + 1, oy), (ox - 1, oy)):
            d = dist.get(nxt)
            if d is not None and (best_d is None or d < best_d):
                best_d, hookup = d, nxt
        if hookup is None:
            continue
        # Belts are titanium *and* permanent cost scale (+1% each, forever);
        # walking only costs turns. Weight them accordingly. The walk term is
        # also what keeps several builders running this same greedy rule from
        # all converging on the single cheapest ore tile.
        walk = int(((ox - fx) ** 2 + (oy - fy) ** 2) ** 0.5)
        # A builder's scarcest resource is turns, not titanium. `max_walk` says
        # "only mine what is nearly free from where you already are" -- without
        # it a builder will trek back across the map for one harvester, which is
        # a siege it is not prosecuting for twenty turns.
        if max_walk is not None and walk > max_walk:
            continue
        key = (4 * best_d + walk, best_d, ox, oy)
        if best_key is None or key < best_key:
            best_key = key
            best_ore = ore
            best_hookup = hookup

    if best_ore is None:
        return None

    belts: list[Position] = []
    cursor = best_hookup
    while dist[cursor] > 0:
        belts.append(Position(cursor[0], cursor[1]))
        cursor = parent[cursor]
    belts.reverse()
    # `cursor` is now a network tile: what the first new belt hooks onto.
    return Plan(best_ore, belts, Position(cursor[0], cursor[1]))
