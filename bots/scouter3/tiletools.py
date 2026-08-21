from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError
from encodeparse import CARDINALS
from mapclass import Map

def tiles_to_attack_with_sentinel_from(target: Position) -> list[Position]:
    tiles = []
    for direction in Direction:
        active_tile = target.add(direction)
        for i in range(4):
            tiles.append(active_tile)
            active_tile = active_tile.add(direction)
        if direction in CARDINALS: tiles.append(active_tile)
    return tiles

def tiles_to_attack_core_map_mode(core_tiles: list[Position], map: Map) -> list[Position]:
    tiles = []
    for core_tile in core_tiles:
        possible = tiles_to_attack_with_sentinel_from(core_tile)
        for tile in possible:
            if tile not in core_tiles and map.get_environment_at(tile) == Environment.EMPTY:
                tiles.append(tile)
    return tiles

def tiles_to_attack_core_ct_mode(core_tiles: list[Position], ct: Controller) -> list[Position]:
    usable_tiles = []
    visible_tiles = ct.get_nearby_tiles()
    for core_tile in core_tiles:
        possible = tiles_to_attack_with_sentinel_from(core_tile)
        for tile in possible:
            if tile.x < 0 or tile.x >= ct.get_map_width() or tile.y < 0 or tile.y >= ct.get_map_height(): continue
            if tile in visible_tiles and not ct.is_tile_empty(tile): continue
            if tile not in core_tiles: usable_tiles.append(tile)
    return usable_tiles

def tiles_in_crosshair(ct: Controller) -> list[Position]:
    facing_dir = ct.get_direction()
    active_tile = ct.get_position().add(facing_dir)
    targets = []
    while ct.is_in_vision(active_tile):
        targets.append(active_tile)
        active_tile = active_tile.add(facing_dir)
    return targets

def tile_has_enemy(tile: Position, ct: Controller) -> bool:
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team():
        return True
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_builder_bot_id(tile)) != ct.get_team():
        return True
    return False

def tile_has_enemy_core(tile: Position, ct: Controller) -> bool:
    return ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) != ct.get_team() and ct.get_entity_type(ct.get_tile_building_id(tile)) == EntityType.CORE

def tile_has_friend(tile: Position, ct: Controller) -> bool:
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_building_id(tile)) == ct.get_team():
        return True
    if ct.get_tile_building_id(tile) and ct.get_team(ct.get_tile_builder_bot_id(tile)) == ct.get_team():
        return True
    return False

def sentinel_could_hit_opp_core_from(tile: Position, opp_core_tiles: list[Position], ct: Controller) -> Direction | None:
    for direction in Direction:
        for core_tile in opp_core_tiles:
            if ct.can_fire_from(tile, direction, EntityType.SENTINEL, core_tile):
                return direction
    return None

def adjacent_tiles(tile: Position) -> list[Position]:
    return [tile.add(direction) for direction in CARDINALS]

if __name__ == '__main__':
    print("HI")