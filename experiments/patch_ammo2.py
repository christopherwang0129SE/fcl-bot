#!/usr/bin/env python3
"""Size the ammo pool from measured demand, not from threat near our own core.

Measured: sentinels had a live target but could not fire 135 of 177 times on
ragnarok, and 68-73 of those blocks were an empty ammo pool (vs ~20 for reload).
We hold a flat 20 ammo -- two sentinel shots -- while fielding ~7 sentinels.

The previous attempt scaled the buffer by enemies near OUR core, which almost
never triggers: our sentinels are forward, besieging THEIRS. The core cannot see
those turrets, and every store slot is taken, so infer demand instead: watch how
much ammo actually drains each round and keep a buffer that covers it. Ammo
falling to zero means shots were missed, so climb fast; a pool sitting untouched
means the titanium is better spent, so decay back down.
"""
import sys
p = sys.argv[1] + "/main.py"
s = open(p, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "# Ammo pool bounds. A sentinel shot costs 10, a gunner shot 4.\n"
              "AMMO_FLOOR = 20\n"
              "AMMO_CEILING = 120\n"
              "# Rounds of idle pool before we stop reserving titanium for it.\n"
              "AMMO_DECAY_ROUNDS = 25", 1)

s = s.replace("        self.ammo_needed = 20",
              "        self.ammo_needed = AMMO_FLOOR\n"
              "        self.prev_ammo = 0\n"
              "        self.idle_ammo_rounds = 0", 1)

old = """        if ct.get_global_ammo() < self.ammo_needed:
            if ct.can_convert_ammo(self.ammo_needed):
                ct.convert_ammo(self.ammo_needed)"""
new = """        # Size the pool from demand, but treat an EMPTY pool as the strongest
        # demand signal there is: when starved nothing burns, so a controller
        # driven by burn alone reads 'no demand' and starves us further.
        ammo = ct.get_global_ammo()
        burned = max(0, self.prev_ammo - ammo)
        if ammo == 0 and self.prev_ammo == 0:
            self.ammo_needed = min(AMMO_CEILING, max(self.ammo_needed * 2, AMMO_FLOOR * 2))
            self.idle_ammo_rounds = 0
        elif burned:
            self.ammo_needed = min(AMMO_CEILING, max(self.ammo_needed, burned * 4))
            self.idle_ammo_rounds = 0
        else:
            self.idle_ammo_rounds += 1
            if self.idle_ammo_rounds > AMMO_DECAY_ROUNDS:
                self.ammo_needed = AMMO_FLOOR
                self.idle_ammo_rounds = 0

        # Convert what we can actually afford. can_convert_ammo() is all-or-
        # nothing, so asking for an unaffordable shortfall converts NOTHING --
        # which is how a bigger buffer can leave the turrets drier than a small
        # one. Keep a builder bot in reserve so ammo never blocks spawning.
        spare = ct.get_global_resources() - ct.get_builder_bot_cost()
        amount = min(self.ammo_needed - ammo, spare)
        if amount > 0 and ct.can_convert_ammo(amount):
            ct.convert_ammo(amount)
            ammo += amount
        self.prev_ammo = ammo"""
assert s.count(old) == 1, "ammo anchor"
s = s.replace(old, new, 1)
open(p, "w", newline="").write(s)
print(f"patched {p}")
