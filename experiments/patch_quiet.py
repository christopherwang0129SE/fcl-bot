#!/usr/bin/env python3
"""Strip per-unit-per-round debug output from a bot.

`print()` is captured into the replay and `draw_indicator_*()` into the replay's
overlay, and both are charged to the 10ms per-unit CPU budget. Removing this
spam was one of the measured wins in v4; the scouter3/scouter4 line reintroduced
it and carries 64 print sites and 10 draw_indicator sites, several of them
f-strings evaluated every turn for every unit.

Only statements whose whole line is a print/draw_indicator call are removed, so
nothing that also performs work is touched. Lines that would leave an empty
block get `pass` instead. Bodies under `if __name__ == '__main__'` are left
alone -- they never run in a match.

  python3 patch_quiet.py <botdir>
"""
import re, sys

d = sys.argv[1]
CALL = re.compile(r"^(\s*)(print|ct\.draw_indicator_dot|ct\.draw_indicator_line)\s*\(")
# `else: print(...)` and `if x: print(...)` collapse to a no-op branch
INLINE = re.compile(r"^(\s*)(else|elif .*|if .*|for .*|while .*):\s*(print|ct\.draw_indicator_\w+)\s*\(.*\)\s*$")

for name in ("main.py", "tiletools.py", "encodeparse.py", "mapclass.py"):
    p = "%s/%s" % (d, name)
    try:
        raw = open(p, newline="").read()
    except FileNotFoundError:
        continue
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")

    out, removed, in_main = [], 0, False
    for line in lines:
        if line.startswith("if __name__"):
            in_main = True
        elif line and not line[0].isspace():
            in_main = False
        if in_main:
            out.append(line)
            continue

        m = INLINE.match(line)
        if m:
            out.append("%s%s: pass" % (m.group(1), m.group(2)))
            removed += 1
            continue
        m = CALL.match(line)
        if m and line.rstrip().endswith(")") and line.count("(") == line.count(")"):
            out.append("%spass" % m.group(1))
            removed += 1
            continue
        out.append(line)

    open(p, "w", newline="").write(nl.join(out))
    print("%s: removed %d debug statements" % (name, removed))
