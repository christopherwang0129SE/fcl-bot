from collections import deque
from fcode import Environment, Direction, Position
from mapclass import Map

CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]


def bfs_path(map_obj: Map, start: Position, goal: Position, max_nodes: int = 1000, blocked: set | None = None) -> list[Direction] | None:
    """Find the shortest path from start to goal using BFS.

    Treats Environment.WALL as blocked; everything else (EMPTY, ORE_TITANIUM, unscouted 0) is passable.
    Returns a list of Directions to move, or None if unreachable or goal == start.
    Caps search to max_nodes to avoid excessive CPU usage.
    """
    if start == goal or not map_obj.configured:
        return None

    queue = deque([(start, [])])
    visited = {start}
    nodes_explored = 0

    while queue and nodes_explored < max_nodes:
        pos, path = queue.popleft()
        nodes_explored += 1

        if pos == goal:
            return path

        for direction in CARDINALS:
            next_pos = pos.add(direction)
            if next_pos in visited:
                continue
            if not (0 <= next_pos.x < map_obj.width and 0 <= next_pos.y < map_obj.height):
                continue
            # Treat WALL as blocked, everything else (including unscouted 0) as passable
            if not map_obj.is_passable(Position(next_pos.x, next_pos.y)):
                continue
            # Tiles seen to be unwalkable -- buildings, the enemy core, a wall
            # of barriers -- are not in the environment grid at all.
            if blocked and next_pos in blocked and next_pos != goal:
                continue

            visited.add(next_pos)
            queue.append((next_pos, path + [direction]))

    return None
