#!/usr/bin/env bash
source /var/home/student/.venvs/fcode/bin/activate
SCRATCH=/tmp/claude-1000/-var-home-student-Florent-fcl-bot/1835b283-949e-4029-a65c-72072635a08c/scratchpad
cd /var/home/student/Florent/fcl-bot
for v in base vcap1; do
  tot=0; fired=0; noammo=0
  for m in ragnarok midgard archipelago drumlin nordkap valkyrie; do
    for sd in 3 7; do
      log=$(fcode run $SCRATCH/${v}_fp $SCRATCH/base maps/$m.map26 --tle 0 --seed $sd --replay $SCRATCH/f_$v.replay26 --json 2>&1 >/dev/null)
      tot=$((tot + $(echo "$log" | grep -acE "^(FIRED|NOAMMO|RELOAD)")))
      fired=$((fired + $(echo "$log" | grep -ac "^FIRED")))
      noammo=$((noammo + $(echo "$log" | grep -ac "^NOAMMO")))
    done
  done
  pct=$(python3 -c "print(f'{100*$fired/max($tot,1):.1f}')")
  echo "  $v: opportunities=$tot  fired=$fired (${pct}%)  blocked-by-ammo=$noammo"
done
echo FP-DONE
