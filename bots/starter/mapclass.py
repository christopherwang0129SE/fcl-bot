from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError


def pack_pos(pos: Position) -> int:
    """Encode a position into a single u32 for the communication store.
    We offset by +1 so that position (0, 0) doesn't encode as 0, which we reserve to mean 'no data'."""
    return ((pos.x + 1) << 16) | (pos.y + 1)


def unpack_pos(val: int) -> Position | None:
    """Decode a position from the communication store. Returns None if empty (0)."""
    if val == 0:
        return None
    return Position((val >> 16) - 1, (val & 0xFFFF) - 1)


class Map:
    """Stores and manages map data, location of obstacles and resources
    possibly structures units and pathfinding pre-compute"""

    def __init__(self):
        """Creates an map-object unusable until configured"""
        self.terrain_grid = None
        self.height = None
        self.width = None
        self.configured = False

    def configure(self, width: int, height: int) -> None:
        """Sets the map as configured and creates a grid of Zeroes to represent unscouted terrain"""
        self.width = width
        self.height = height
        self.configured = True
        self.terrain_grid = [[0 for col in range(width)] for row in range(height)]

    def __str__(self) -> str:
        if not self.configured: return "Map not configured!"
        return "\n".join(" ".join('*' if x == 0 else str(x.name)[0] for x in row) for row in self.terrain_grid)

    def set_environment_at(self, pos: Position, env: Environment) -> None:
        #Sets the specified position if valid, else does nothing
        if (not self.configured) or pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height: return
        self.terrain_grid[pos.y][pos.x] = env

    def get_environment_at(self, pos: Position) -> int | None:
        if (not self.configured) or pos.x<0 or pos.x>=self.width or pos.y<0 or pos.y>=self.height: return None
        return self.terrain_grid[pos.y][pos.x]

    def scouted_at(self, pos: Position) -> bool:
        if self.get_environment_at(pos): return True
        return False

    def nearest_unscouted(self, from_pos: Position, max_radius: int = 10) -> Position | None:
        """Scan outward from from_pos in a spiral/ring pattern, returning the first unscouted cell within max_radius.
        Returns None if all cells within the radius have been scouted."""
        if not self.configured:
            return None
        for radius in range(1, max_radius + 1):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    pos = Position(from_pos.x + dx, from_pos.y + dy)
                    if 0 <= pos.x < self.width and 0 <= pos.y < self.height:
                        if self.terrain_grid[pos.y][pos.x] == 0:
                            return pos
        return None


if __name__ == '__main__':
    e_map = Map()
    e_map.configure(3,5)
    e_map.set_environment_at(Position(2,2), Environment.WALL)
    e_map.set_environment_at(Position(1, 2), Environment.EMPTY)
    e_map.set_environment_at(Position(1, 1), Environment.ORE_TITANIUM)
    print(e_map)
