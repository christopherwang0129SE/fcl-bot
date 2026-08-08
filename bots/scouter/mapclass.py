from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError


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


if __name__ == '__main__':
    e_map = Map()
    e_map.configure(3,5)
    e_map.set_environment_at(Position(2,2), Environment.WALL)
    e_map.set_environment_at(Position(1, 2), Environment.EMPTY)
    e_map.set_environment_at(Position(1, 1), Environment.ORE_TITANIUM)
    print(e_map)
