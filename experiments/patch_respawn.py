#!/usr/bin/env python3
"""Replace builder bots that die. The live bot never does.

`self.bots_made` only ever increments, and the spawn gate is
`if self.bots_made < 4`, so once four builders have *ever* existed the core
will not make another one no matter how many are killed. An opponent that
kills builders therefore takes them off the board permanently: we lose the
siege, the economy and the scouting for the rest of the match, with thousands
of titanium banked. The only escape hatch today is the `core hp < max` clause,
which tops up to six -- it fires only once our core is already being hit.

A mirror A/B is blind to this, because both sides lose builders at the same
rate and it cancels; the ladder (6-19 against real opponents) is not.

Death detection is free and already half-built: `read_stored_scout` zeroes a
builder's scout slot after reading it, so a live builder is exactly one that
rewrites its slot each round. The one gap is that a builder which did not move
writes a literal 0, which is indistinguishable from silence -- so it now writes
a nonzero heartbeat instead. The heartbeat decodes to Position(0,0) with no
scouted tiles, i.e. byte-for-byte the same information the core got before, so
this does NOT quietly fix the load-bearing `Position(0, 0)` bug.

A replacement adopts the dead builder's identity (and therefore its store
slots) via a new field in the game-data word, and the core frees that
identity's build-order slot so a fresh order is issued.

  python3 patch_respawn.py <botdir> [death_rounds]
"""
import sys

d = sys.argv[1]
death_rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3

p = d + "/main.py"
raw = open(p, newline="").read()
nl = "\r\n" if "\r\n" in raw else "\n"
s = raw.replace("\r\n", "\n")


def sub(old, new):
    global s
    assert s.count(old) == 1, "anchor: " + old.strip().split("\n")[0][:60]
    s = s.replace(old, new, 1)


# --- a builder that stands still still says it is alive ----------------------
sub("""        if self.moved_direction is None: #Write only environment-scout if moved
            ct.write_store(self.scout_store_slot, 0)""",
    """        if self.moved_direction is None: #Write only environment-scout if moved
            # Nonzero so the core can tell "did not move" from "is dead", but
            # chosen to decode to Position(0,0) with zero scouted tiles -- the
            # exact same information a literal 0 carried before.
            ct.write_store(self.scout_store_slot, HEARTBEAT)""")

sub("""def encode_scout(""",
    """HEARTBEAT = 1 << 18  # decodes to Position(0,0), no tiles: "alive, no news"


def encode_scout(""")

# --- game data carries the identity the next builder should adopt ------------
sub("""def encode_game_data(bots_made: int, opp_core_bottom_right: Position) -> int:
    \"\"\"Encodes game data\"\"\"
    data_number = bots_made
    if opp_core_bottom_right is not None:
        data_number += (opp_core_bottom_right.x << 10) + (opp_core_bottom_right.y << 5)
    return data_number""",
    """def encode_game_data(bots_made: int, opp_core_bottom_right: Position, adopt_identity: int = 0) -> int:
    \"\"\"Encodes game data\"\"\"
    data_number = bots_made + (adopt_identity << 15)
    if opp_core_bottom_right is not None:
        data_number += (opp_core_bottom_right.x << 10) + (opp_core_bottom_right.y << 5)
    return data_number""")

# both parse_game_data_number and parse_game_data share this tail
old_tail = """    opp_core_bottom_right_y = (data_number & (31 << 5)) >> 5
    return [builders_made, Position(opp_core_bottom_right_x, opp_core_bottom_right_y)]"""
new_tail = """    opp_core_bottom_right_y = (data_number & (31 << 5)) >> 5
    adopt_identity = (data_number & (7 << 15)) >> 15
    return [builders_made, Position(opp_core_bottom_right_x, opp_core_bottom_right_y), adopt_identity]"""
assert s.count(old_tail) == 2, "game-data parse anchors"
s = s.replace(old_tail, new_tail)

# --- a replacement takes over the dead builder's number and slots ------------
sub("""        game_data = parse_game_data(ct)
        self.am_builder_number = game_data[0]""",
    """        game_data = parse_game_data(ct)
        # The core hands a replacement the identity of the builder it lost, so
        # it inherits that builder's scout and build-order slots.
        self.am_builder_number = game_data[2] or game_data[0]""")

# --- core state --------------------------------------------------------------
sub("""        self.builder_positions: list[Position|None] = [None, None, None]""",
    """        self.builder_positions: list[Position|None] = [None, None, None]
        self.builder_seen = [False, False, False, False]
        self.builder_missing = [0, 0, 0, 0]
        self.replace_identity: int|None = None
        self.pending_identity: int|None = None
        self.pending_since = 0""")

# --- core reads liveness before it zeroes the slots --------------------------
sub("""        for i in range(0,min(3,self.bots_made)):
            scout_slot = 14 - 4*i
            self.builder_positions[i] = read_stored_scout(scout_slot, ENV_MAP, ct)
            read_stored_scout(3, ENV_MAP, ct) #Bot 4 is special""",
    """        alive_now = [False, False, False, False]
        if self.bots_made >= 4:
            alive_now[3] = ct.read_store(3) != 0
        for i in range(0,min(3,self.bots_made)):
            scout_slot = 14 - 4*i
            alive_now[i] = ct.read_store(scout_slot) != 0  # before it is zeroed
            self.builder_positions[i] = read_stored_scout(scout_slot, ENV_MAP, ct)
            read_stored_scout(3, ENV_MAP, ct) #Bot 4 is special
        self._track_builder_deaths(alive_now, ct)""")

# --- the tracker -------------------------------------------------------------
sub("""    def _bot_pathfind(self, target: Position, ct: Controller) -> None:""",
    """    def _track_builder_deaths(self, alive_now: list, ct: Controller) -> None:
        \"\"\"A live builder rewrites its scout slot every round and the core
        zeroes it after reading, so a slot still empty next round means that
        builder is gone. Identities are only watched once they have reported at
        least once, which covers the round between spawning and first report.\"\"\"
        for i in range(4):
            if alive_now[i]:
                self.builder_seen[i] = True
                self.builder_missing[i] = 0
                if self.pending_identity == i + 1:
                    self.pending_identity = None
            elif self.builder_seen[i]:
                self.builder_missing[i] += 1
        if self.pending_identity is not None and ct.get_current_round() - self.pending_since > 15:
            self.pending_identity = None  # the replacement died before reporting
        if self.pending_identity is None:
            self.replace_identity = None
            for i in range(4):
                if self.builder_missing[i] >= %d:
                    self.replace_identity = i + 1
                    self.builder_missing[i] = 0
                    self.builder_seen[i] = False
                    break

    def _bot_pathfind(self, target: Position, ct: Controller) -> None:""" % death_rounds)

# --- spawn the replacement ---------------------------------------------------
sub("""        if self.bots_made < 4:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(Position(ct.get_map_width()//2, ct.get_map_height()//2))): #spawn extra bots towards center""",
    """        if self.replace_identity and self.pending_identity is None:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(Position(ct.get_map_width()//2, ct.get_map_height()//2))):
                if ct.can_spawn(pos):
                    ct.spawn_builder(pos)
                    self.pending_identity = self.replace_identity
                    self.pending_since = ct.get_current_round()
                    if self.replace_identity <= 3:  # bot 4 has no build order
                        ct.write_store(19 - 4*self.replace_identity, 0)
                    self.replace_identity = None
                    break

        if self.bots_made < 4:
            for pos in sorted(ct.get_nearby_tiles(dist_sq=2), key=lambda tile: tile.distance_squared(Position(ct.get_map_width()//2, ct.get_map_height()//2))): #spawn extra bots towards center""")

sub("""        ct.write_store(SLOT_GAME_DATA,encode_game_data(self.bots_made, self.opp_core_bottom_right))""",
    """        # Publish the adopted identity only on the round we actually spawn the
        # replacement. Store writes are buffered, so that is exactly the value the
        # new builder reads on its first turn -- and leaving it up any longer would
        # let the next damage-response builder adopt the same identity and collide
        # on its store slots.
        adopt = self.pending_identity if self.pending_identity and ct.get_current_round() == self.pending_since else 0
        ct.write_store(SLOT_GAME_DATA,encode_game_data(self.bots_made, self.opp_core_bottom_right, adopt))""")

open(p, "w", newline="").write(s.replace("\n", nl))
print("respawn (death after %d silent rounds) -> %s" % (death_rounds, d))
