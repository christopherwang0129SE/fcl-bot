from random import choice
from fcode import Controller, Team, EntityType, Environment, Direction, Position, GameError
from mapclass import Map, print_conveyor_info
from encodeparse import (encode_entities, parse_entities, encode_scout, parse_scout, encode_game_data, parse_game_data_number,
                         parse_game_data, read_stored_env_scout, read_stored_scout, encode_build_order, parse_build_order)
from encodeparse import CARDINALS, Environments, SCOUT_EDGE_OFFSETS, SCOUT_CLOSE_CROSS_OFFSETS, SCOUT_FAR_CROSS_OFFSETS, SLOT_GAME_DATA
from tiletools import tiles_to_attack_with_sentinel_from, tiles_to_attack_core_map_mode, tiles_to_attack_core_ct_mode, tiles_in_crosshair, tile_has_enemy, tile_has_friend, tile_has_enemy_core, sentinel_could_hit_opp_core_from, adjacent_tiles
ENV_MAP = Map()


"""
0 (GAME DATA): OppCoreBottom (10-bit) builders_made (5-bit)

1 (B4): Entities scout far (32-bit)
2 (B4): Entities scout close (32-bit)
3 (B4) Environment scout (32-bit)

4-7 (B3)
8-11 (B2)
12 (B1): Entities scout far (32-bit)
13 (B1): Entities scout close (32-bit)
14 (B1): Environment scout (32-bit)
15 (B1): Buildorder (31-bit)
"""

class Player:
    def __init__(self):

        #BUILDERS
        self.am_builder_number = -1
        self.scout_store_slot = -1
        self.build_order_slot = -1
        self.build_stage: int = -1
        self.path_index: int = 0
        self.conveyor_path: list[Direction] = []
        self.build_direction: Direction|None = None
        self.build_type_n: int = 0
        self.follow_path: Direction|None = None

        #CORE
        self.bots_made = 0
        self.ammo_needed = 20
        self.builder_positions: list[Position|None] = [None, None, None]
        self.build_orders_made: list[tuple[Position, int]] = []

        #ALL
        self.own_core_tiles = []
        self.opp_core_tiles = []
        self.opp_core_bottom_right = None

    def run(self, ct: Controller) -> None:

        if self.opp_core_bottom_right is None:
            self._learn_opp_core(ct)
        etype = ct.get_entity_type()

        if etype == EntityType.CORE:
            self._run_core(ct)

        elif etype == EntityType.BUILDER_BOT:
            if self.am_builder_number < 0: self._configure_builder(ct)
            print(f"BUILDER_BOT: {self.am_builder_number}\n {self.build_stage=}")
            self._run_builder(ct)

        elif etype == EntityType.SENTINEL:
            self._run_sentinel(ct)

    #TURRETS

    def _run_sentinel(self, ct: Controller) -> None:
        if self.opp_core_tiles is None:
            self._configure_turret(ct)
        target = None
        print(f"attackable: {ct.get_attackable_tiles()}")
        for tile in ct.get_attackable_tiles():
            if tile_has_enemy_core(tile, ct):
                target = tile
        if not target:
            for tile in ct.get_attackable_tiles():
                if tile_has_enemy(tile, ct):
                    target = tile
        print(f"target={target}")
        if target:
            if ct.can_fire(target):
                ct.fire(target)

    def _configure_turret(self, ct: Controller) -> None:
        game_data = parse_game_data(ct)
        discovered_bottom_core = game_data[1]
        if self.opp_core_bottom_right is None and discovered_bottom_core != Position(0, 0):
            self.opp_core_bottom_right = game_data[1]
            for dx in 0, -1:
                for dy in 0, -1:
                    self.opp_core_tiles.append(
                        Position(discovered_bottom_core.x + dx, discovered_bottom_core.y + dy))

    #CORE
    def _core_configure_map(self, ct: Controller) -> None:
        """Sets the parameters of the ENV_MAP and reads the cores own scouting into it"""
        ENV_MAP.configure(ct.get_map_width(), ct.get_map_height(), ct.get_position())

        for tile in ct.get_nearby_tiles():
            ENV_MAP.set_environment_at(tile, ct.get_tile_env(tile))
            ct.draw_indicator_dot(tile, 0, 255, 0)
            if ct.get_tile_building_id(tile) and ct.get_tile_building_id(tile) == ct.get_id():
                self.own_core_tiles.append(tile)
        ENV_MAP.update_conveyor_distance_grid()
            
    def _run_core(self, ct: Controller) -> None:

        if ct.get_global_ammo() < self.ammo_needed:
            if ct.can_convert_ammo(self.ammo_needed):
                ct.convert_ammo(self.ammo_needed)

        if not ENV_MAP.configured:
            self._core_configure_map(ct)

        for i in range(0,min(3,self.bots_made)):
            scout_slot = 14 - 4*i
            self.builder_positions[i] = read_stored_scout(scout_slot, ENV_MAP, ct)
            read_stored_scout(3, ENV_MAP, ct) #Bot 4 is special

        ENV_MAP.update_conveyor_distance_grid()
        if ENV_MAP.known_symmetry is None:
            if ENV_MAP.discover_symmetry():
                ENV_MAP.deduce_opp_core()
                self.opp_core_tiles = ENV_MAP.opp_core
                self.opp_core_bottom_right = max(self.opp_core_tiles, key=lambda tile: tile.x+tile.y)

        if len(self.opp_core_tiles)==0:
            if len(ENV_MAP.opp_core)==4:
                self.opp_core_tiles = ENV_MAP.opp_core
                self.opp_core_bottom_right = max(self.opp_core_tiles, key=lambda tile: tile.x + tile.y)

        attempted_ores = []
        for i in range(0,3-len(self.build_orders_made)):
            if not ENV_MAP.unplanned_ore: break
            possible, go_to, build_direction, build_type, conveyor_path = ENV_MAP.plan_easiest_harvester(attempted_ores)
            if not possible:
                print(f"PLAN FAILED {go_to}")
                attempted_ores.append(go_to)
            else:
                print(f"PLAN MADE {go_to=}\n{[dir.name[0] for dir in conveyor_path]}")
                build_order_number = encode_build_order(go_to, build_type, build_direction,
                                                        conveyor_path)
                self.build_orders_made.append((go_to,build_order_number))
                for ticket in self.build_orders_made:
                    if ticket is not None: ct.draw_indicator_dot(ticket[0], 255, 0,0)

        for i in range(0,min(3,self.bots_made+1)):#Plan also the new bot
            order_slot = 15 - 4*i
            if ct.read_store(order_slot) == 0:  # Need order
                bot_pos = self.builder_positions[i] if self.builder_positions[i] else ct.get_position() #core position
                dist = 63
                best_ticket = None
                for ticket in self.build_orders_made:
                    ticket_distance = ticket[0].distance_squared(bot_pos)
                    if ticket_distance < dist:
                        dist = ticket_distance
                        best_ticket = ticket
                if best_ticket:
                    print(f"ASSIGNING BUILDER {i + 1}: {best_ticket[0]}")
                    ct.write_store(order_slot, best_ticket[1])
                    if i == self.bots_made:
                        for tile in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(best_ticket[0])):
                            if ct.can_spawn(tile):
                                ct.spawn_builder(tile)
                                self.bots_made += 1
                                break
                    self.build_orders_made.remove(best_ticket)

        if self.bots_made < 4:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(Position(ct.get_map_width()//2, ct.get_map_height()//2))): #spawn extra bots towards center
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.bots_made += 1
                    break

        if ct.get_hp() < ct.get_max_hp() and self.bots_made < 6:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(
                Position(ct.get_map_width() // 2, ct.get_map_height() // 2)), reverse=True):  # spawn extra healers towards back
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.bots_made += 1
                    break

        ct.write_store(SLOT_GAME_DATA,encode_game_data(self.bots_made, self.opp_core_bottom_right))
        #print_conveyor_info(ENV_MAP)

    #BUILDERBOTS

    def _generate_move_path(self, target: Position, ct: Controller) -> Direction:
            bot_pos = ct.get_position()
            visible_tiles = ct.get_nearby_tiles()
            opened = sorted([tile for tile in adjacent_tiles(bot_pos) if tile in visible_tiles and ct.is_tile_passable(tile)], key=lambda tile: tile.distance_squared(target), reverse=True)
            if target in opened: return bot_pos.cardinal_direction_to(target)
            parents = {}
            for tile in opened: parents[tile] = bot_pos
            path = []

            while opened:
                active_tile = opened.pop()
                neighbors = [tile for tile in adjacent_tiles(active_tile) if tile in visible_tiles and ct.is_tile_passable(tile)]
                for tile in neighbors:
                    if tile not in parents and tile not in opened:
                        parents[tile] = active_tile
                        opened.append(tile)
                if target in parents:
                    tile = target
                    while tile in parents:
                        path.append(tile)
                        tile = parents[tile]
                    print(f"Generated path: {path}")
                    return bot_pos.cardinal_direction_to(path.pop())
                opened.sort(key=lambda tile: tile.distance_squared(target), reverse=True)
            return False

    def _bot_pathfind(self, target: Position, ct:Controller) -> None:
        """Moves toward target based on own vision, moves and updates self.moved_direction"""
        visible_tiles = ct.get_nearby_tiles()

        if target not in visible_tiles:
            target = min(visible_tiles, key=lambda tile: tile.distance_squared(target) if ct.is_tile_passable(tile) else 2047)
        print(f"Pathfind: {target=}")
        if not ct.is_tile_passable(target):
            pass # TODO handle this
        suggested_move = self._generate_move_path(target, ct)
        if not suggested_move:
            print("Pathfinding failed")
            options = [tile for tile in adjacent_tiles(ct.get_position()) if ct.can_move(ct.get_position().cardinal_direction_to(tile))]
            print(f"{options=}")
            if options: suggested_move = ct.get_position().cardinal_direction_to(min(options, key=lambda tile: tile.distance_squared(target)))

        if suggested_move:
            if ct.can_move(suggested_move):
                ct.move(suggested_move)
                self.moved_direction = suggested_move


    def _execute_buildplan(self, ct: Controller):
        bot_position = ct.get_position()
        if self.build_stage == 0 and len(self.conveyor_path) == 0: self.build_stage = 1
        if self.build_stage == 0:  # Has not yet built first conveyor
            print(f"STAGE 0, {self.go_to=}")
            if bot_position == self.go_to:  # Make any move:
                for direction in CARDINALS:
                    if ct.can_move(direction):
                        ct.move(direction)
                        self.moved_direction = direction
                        break

            elif self.go_to in adjacent_tiles(bot_position):
                if ct.can_build_conveyor(self.go_to, self.conveyor_path[self.path_index]):
                    ct.build_conveyor(self.go_to, self.conveyor_path[self.path_index])
                    self.path_index += 1
                    self.build_stage = 1
                else:
                    blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))
                    if blocked_by_id and (ct.get_team() != ct.get_team(blocked_by_id)):
                        if ct.can_fire(bot_position.add(self.build_direction)):
                            ct.fire(bot_position.add(self.build_direction))
            else:
                self._bot_pathfind(self.go_to, ct)

        elif self.build_stage == 1:  # Has not built harvester
            print(f"STAGE 1")
            if bot_position != self.go_to:
                self._bot_pathfind(self.go_to, ct)
            elif self.build_type_n == 0: self.build_stage = 2
            else:
                if ct.can_build_harvester(self.go_to.add(self.build_direction)):
                    ct.build_harvester(self.go_to.add(self.build_direction))
                    self.build_stage = 2
                else:
                    blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))
                    if blocked_by_id and (ct.get_team() != ct.get_team(blocked_by_id)):
                        if ct.can_fire(bot_position.add(self.build_direction)):
                            ct.fire(bot_position.add(self.build_direction))

        if self.build_stage == 2:  # Has built harvester and first conveyor
            if len(self.conveyor_path) == self.path_index:
                print("\nBUILD COMPLETE")
                ct.write_store(self.build_order_slot,0)
                self.build_stage = -1
                self.follow_path = None
                return True
            if self.follow_path:
                if ct.can_move(self.follow_path):
                    ct.move(self.follow_path)  # TODO else?
                    self.moved_direction = self.follow_path
                    self.follow_path = None

            else:
                direction_next = self.conveyor_path[self.path_index - 1]
                next_tile = bot_position.add(direction_next)  # pointed from last built conveyor

                if ct.can_build_conveyor(next_tile, self.conveyor_path[self.path_index]):
                    ct.build_conveyor(next_tile, self.conveyor_path[self.path_index])
                    self.path_index += 1
                    self.follow_path = direction_next
                    if len(self.conveyor_path) == self.path_index:
                        print("\nBUILD COMPLETE")
                        ct.write_store(self.build_order_slot, 0)
                        self.build_stage = -1
                        self.follow_path = None
                        return True
                else:
                    blocked_by_id = ct.get_tile_building_id(bot_position.add(self.build_direction))
                    if blocked_by_id and (ct.get_team() != ct.get_team(blocked_by_id)):
                        if ct.can_fire(bot_position.add(self.build_direction)):
                            ct.fire(bot_position.add(self.build_direction))

    def _configure_builder(self, ct: Controller) -> None:
        """The builder finds out who it is from store(game_data), the first 3 bots get scouting slots and build_orders"""
        game_data = parse_game_data(ct)
        self.am_builder_number = game_data[0]
        if self.am_builder_number < 4:
            self.build_order_slot = 19 - 4 * self.am_builder_number
            self.scout_store_slot = 18 - 4 * self.am_builder_number
        elif self.am_builder_number == 4:
            self.scout_store_slot = 3
        if not self.own_core_tiles:
            for tile in ct.get_nearby_tiles():
                if id := ct.get_tile_building_id(tile):
                    if ct.get_entity_type(id) == EntityType.CORE:
                        if ct.get_team(id):
                            self.own_core_tiles.append(tile)

    def _read_build_order(self, ct: Controller) -> None:
        """Reads build-order from ct.store"""
        self.go_to, self.build_type_n, self.build_direction, self.conveyor_path = parse_build_order(ct.read_store(self.build_order_slot))
        self.build_stage, self.path_index = 0,0

    def _push_to_opposite_corner(self, ct: Controller) -> None:
        core_tile = self.own_core_tiles[0]
        other_side_x = ct.get_map_width() - core_tile.x
        other_side_y = ct.get_map_height() - core_tile.y
        self._bot_pathfind(Position(other_side_x, other_side_y), ct)

    def _bot_without_orders(self, ct: Controller) -> None:
        """When the builder does not have an order it can do this"""
        print("BOT WITHOUT ORDERS")
        pos = ct.get_position()

        if self.opp_core_bottom_right is None:
            self._push_to_opposite_corner(ct)

        for tile in adjacent_tiles(pos):
            if ct.can_heal(tile):
                print("HEALER")
                ct.heal(tile)
                return

        if self.opp_core_tiles:
            for tile in adjacent_tiles(pos):
                if ct.can_build_sentinel(tile, Direction.NORTH):
                    orientation = sentinel_could_hit_opp_core_from(tile, self.opp_core_tiles, ct)
                    if orientation:
                        ct.build_sentinel(tile, orientation)
                        return

            attack_tiles = tiles_to_attack_core_ct_mode(self.opp_core_tiles, ct)
            for tile in attack_tiles:
                ct.draw_indicator_dot(tile, 255,255,0)
            best_tile = min(attack_tiles, key=lambda tile: tile.distance_squared(pos))
            ct.draw_indicator_dot(best_tile, 255, 155, 255)
            print(f"\nSENTINEL-STAGING {best_tile=}")
            self._bot_pathfind(best_tile, ct)

        open_dirs = [
            d for d in CARDINALS
            if ct.can_move(d) and ct.get_tile_env(pos.add(d)) == Environment.EMPTY
        ]
        move_options = open_dirs or [d for d in CARDINALS if ct.can_move(d)]
        if move_options:
            direction = choice(move_options)
            ct.move(direction)
            self.moved_direction = direction
            print(f"DEFAULT RANDOM MOVE")

    def _report_to_store(self, ct: Controller) -> None:
        """Writes scout data to ct.store"""
        if self.scout_store_slot < 0: return
        if self.moved_direction is None: #Write only environment-scout if moved
            ct.write_store(self.scout_store_slot, 0)
        else:
            scout_n = encode_scout(ct.get_position(), self.moved_direction, ct)
            ct.write_store(self.scout_store_slot, scout_n)
        scout_close_entities_n = encode_entities(ct.get_position(), SCOUT_CLOSE_CROSS_OFFSETS, ct)
        scout_far_entities_n = encode_entities(ct.get_position(), SCOUT_FAR_CROSS_OFFSETS, ct)
        ct.write_store(self.scout_store_slot - 1, scout_close_entities_n)
        ct.write_store(self.scout_store_slot - 2, scout_far_entities_n)

    def _run_builder(self, ct: Controller) -> None:
        self.moved_direction = None

        if self.build_stage < 0 and self.build_order_slot > 0: #Has no build order, and wants one
            if ct.read_store(self.build_order_slot) > 0:
                self._read_build_order(ct)
            else:
                pass
                #print(f"BUILDER {self.am_builder_number} NO ORDER")

        if self.build_stage >= 0:
            self._execute_buildplan(ct)
        else:
            self._bot_without_orders(ct)

        if self.scout_store_slot > 0: self._report_to_store(ct)

    #ALL
    def _learn_opp_core(self, ct: Controller) -> None:

        game_data = parse_game_data(ct)
        discovered_bottom_core = game_data[1]
        print(f"\nLEARNING OPP CORE\n old:{self.opp_core_bottom_right}, new:{discovered_bottom_core}")
        if self.opp_core_bottom_right is None and discovered_bottom_core != Position(0,0):
            self.opp_core_bottom_right = discovered_bottom_core
            for dx in 0, -1:
                for dy in 0, -1:
                    self.opp_core_tiles.append(Position(discovered_bottom_core.x + dx, discovered_bottom_core.y + dy))



if __name__ == '__main__':
    bott = Player()
    print(tiles_to_attack_with_sentinel_from(Position(0,0)))