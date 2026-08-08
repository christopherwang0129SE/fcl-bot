import random

from fcode import Controller, Direction, Environment, EntityType
from mapclass import Map

# Builder bots move only in the four cardinal directions.
CARDINALS = [Direction.NORTH, Direction.SOUTH, Direction.EAST, Direction.WEST]
ENV_MAP = Map()


class Player:
    def run(self, ct: Controller) -> None:
        if not ENV_MAP.configured:
            ENV_MAP.configure(ct.get_map_width(), ct.get_map_height())

        etype = ct.get_entity_type()
        if etype == EntityType.CORE:
            for pos in ct.get_nearby_tiles(dist_sq=2):
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    break
        elif etype == EntityType.BUILDER_BOT:
            self._run_builder(ct)

        self._look_and_update_map(ct)
        print(str(ENV_MAP))

    def _look_and_update_map(self, ct: Controller) -> None:
        nearby_tiles = ct.get_nearby_tiles()
        for tile in nearby_tiles:
            if not ENV_MAP.scouted_at(tile):
                ENV_MAP.set_environment_at(tile, ct.get_tile_env(tile))

    def _run_builder(self, ct: Controller) -> None:
        pos = ct.get_position()
        ct.draw_indicator_dot(pos, 0, 255, 0)

        open_dirs = [
            d for d in CARDINALS
            if ct.can_move(d) and ct.get_tile_env(pos.add(d)) == Environment.EMPTY
        ]
        move_options = open_dirs or [d for d in CARDINALS if ct.can_move(d)]
        if move_options:
            direction = random.choice(move_options)
            ct.move(direction)
            print(f"round {ct.get_current_round()}: moved {direction.name} to {ct.get_position()}")