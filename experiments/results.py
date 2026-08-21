import json, subprocess, sys
FCODE="/var/home/student/.venvs/fcode/bin/fcode"
US="dc7cfe89-627d-44fd-849c-44bc8bfcae40"
out=subprocess.run([FCODE,"match","list","--mine","--limit","40","--json"],
                   capture_output=True,text=True).stdout.strip().split("\n")[-1]
ms={m["id"]:m for m in json.loads(out)["matches"]}
tot_us=tot_them=wins=losses=0
for label,mid in [l.split("=") for l in sys.argv[1:]]:
    m=ms.get(mid)
    if not m:
        print(f"  {label:16s} (not found / pending)"); continue
    if m["teamAId"]==US: ours,theirs,opp = m["scoreA"],m["scoreB"],m["teamBName"]
    else:                ours,theirs,opp = m["scoreB"],m["scoreA"],m["teamAName"]
    ver = m["teamAVersion"] if m["teamAId"]==US else m["teamBVersion"]
    res = "WIN " if ours>theirs else "loss"
    if m["status"]=="complete":
        tot_us+=ours; tot_them+=theirs
        wins += ours>theirs; losses += ours<=theirs
    print(f"  v{ver} vs {opp[:18]:18s} {ours}-{theirs}  {res}  [{m['status']}]")
print(f"  {'TOTAL':21s} {tot_us}-{tot_them} games, {wins}W-{losses}L matches")
