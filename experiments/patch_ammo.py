#!/usr/bin/env python3
"""Dynamic ammo buffer -- scale the pool with actual threat, not a flat 20.

README idea: "Dynamic ammo buffer adjustment based on enemy proximity".

The core tops the shared pool up to a flat 20 forever. A sentinel shot costs 10,
so that is two shots: two sentinels firing drain it and then idle. Conversely,
sitting on 20 ammo while nothing is near the base is titanium that could have
been a harvester.

Threat-driven, deliberately NOT bank-driven -- the bank-driven version was part
of the 32.7% regression because it spent the opening 500 before an economy
existed. Also fixes a real inefficiency in the original: it converted the FULL
buffer amount rather than the shortfall, so a pool at 19/20 converted 20 more.
"""
import sys

path = sys.argv[1] + "/main.py"
s = open(path, newline="").read().replace("\r\n", "\n")

s = s.replace("SLOT_GAME_DATA = 0",
              "SLOT_GAME_DATA = 0\n\n"
              "# Ammo held idle vs. with enemies closing on the core.\n"
              "# A gunner shot costs 4, a sentinel shot 10.\n"
              "AMMO_IDLE = 20\n"
              "AMMO_UNDER_THREAT = 60\n"
              "# Squared radius around the core that counts as 'closing in'.\n"
              "AMMO_THREAT_RADIUS_SQ = 36", 1)

old = """        if ct.get_global_ammo() < self.ammo_needed:
            if ct.can_convert_ammo(self.ammo_needed):
                ct.convert_ammo(self.ammo_needed)"""
new = """        # Hold a deep pool only while something is actually near the base;
        # otherwise that titanium is worth more as a harvester.
        core_pos = ct.get_position()
        threats = 0
        for entity_id in ct.get_nearby_units():
            if ct.get_team(entity_id) == ct.get_team():
                continue
            if ct.get_position(entity_id).distance_squared(core_pos) <= AMMO_THREAT_RADIUS_SQ:
                threats += 1
        self.ammo_needed = AMMO_UNDER_THREAT if threats else AMMO_IDLE

        # Convert the shortfall, not the whole buffer.
        shortfall = self.ammo_needed - ct.get_global_ammo()
        if shortfall > 0 and ct.can_convert_ammo(shortfall):
            ct.convert_ammo(shortfall)"""
assert old in s, "ammo anchor"
s = s.replace(old, new, 1)

open(path, "w", newline="").write(s)
print(f"patched {path}")
