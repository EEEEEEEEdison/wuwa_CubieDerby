# Wuthering Waves Cubie Derby Monte Carlo

Python Monte Carlo simulator for Cubie Derby race outcomes. It ports the original MATLAB script into a reusable CLI and simulation module.

## Quick Start

Run the current finals-lower-half preset:

```powershell
python cubie_derby.py -n 100000 --preset 4 --seed 42
```

Run with Season 2 rules. Season 2 uses a 32-position ring lap, special cells, and the reverse-moving NPC from round 3:

```powershell
python cubie_derby.py --season 2 -n 100000 --start "-3:2;-2:1,4;-1:3,6;0:5" --runners 1 2 3 4 5 6 --seed 42
```

Use a custom known track environment. The lap has positions `0..23`, with `0` as both start and finish. Pre-start positions `-3..-1` are also supported, and runners in the same position are ordered from left to right:

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "-3:10;-2:4,3;0:8" --runners 3 4 8 10 --seed 42
```

Start all selected runners in one cell with a freshly randomized stack order in every simulated race:

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "0:*" --runners 3 4 8 10 --seed 42
```

When every runner starts in position `0`, the first-round action order follows the left-to-right stack order by default. Use `--initial-order random` to override it.

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "0:*" --runners 3 4 8 10 --initial-order random
```

Print machine-readable output:

```powershell
python cubie_derby.py -n 10000 --preset 4 --json
```

For large Monte Carlo runs, enable CPU parallelism. Use `--workers 0` to use all CPU cores, or pass a fixed worker count such as `--workers 4`:

```powershell
python cubie_derby.py -n 100000 --season 2 --start "0:*" --runners 11 12 13 14 15 16 --seed 42 --workers 0
```

Trace one race for rule debugging. Trace output is formatted for reading: each action is separated by blank lines, and skill/special-cell checks are marked with `判定时机` labels.

```powershell
python cubie_derby.py --preset 4 --seed 2 --trace
```

Write one fully traced race to a log file. This is useful for checking Season 2 special cells and NPC movement without running a full Monte Carlo batch:

```powershell
python cubie_derby.py --season 2 --trace-log logs/season2_trace.log --start "-3:2;-2:1,4;-1:3,6;0:5" --runners 1 2 3 4 5 6 --seed 42
```

## Built-In Presets

- `1`: random first-round order, random start stack, 24-position lap.
- `2`: first-round order follows random start stack, 24-position lap.
- `3`: fixed A-group upper-half start/order from the MATLAB script, 24-position lap.
- `4`: fixed finals lower-half start with random first-round order, 24-position lap.
- `5`: fixed A-group lower-half start/order from the MATLAB script, 24-position lap.

Use `--season 2` to apply the Season 2 ruleset to the selected preset or custom start. Without `--lap-length`, Season 2 defaults to a 32-position ring lap.

## Runner IDs

- `13` / `sigrika`: 西格莉卡. From round 2 onward, at round start, marks up to two immediately higher-ranked runners; marked runners move 1 fewer step that round, with a minimum movement of 1.
- `14` / `luuk_herssen`: 陆赫斯. Only on his own turn, forward special cells move his active group 4 cells total; backward special cells move his active group 2 cells backward.
- `15` / `denia`: 达尼娅. If her dice roll matches her previous round's dice roll, she gets +2 steps.
- `16` / `hiyuki`: 绯雪. Each time her movement path and the NPC intersect, including passing through or landing on the NPC's cell, she gains a stacking +1 step bonus for future moves. NPC movement paths are checked the same way.

## Season 2 Rules

- Forward cells: `3`, `11`, `16`, `23`.
- Backward cells: `10`, `28`.
- Shuffle cells: `6`, `20`.
- NPC joins the action order from round 3 at position `0`, rolls with the selected runners, moves backward `1..6` positions on its own turn, is always rightmost when sharing a cell, and returns to `0` at round end unless sharing the last-place runner's cell.

## Output Columns

- `夺冠率`: estimated first-place probability.
- `前三率`: estimated probability of finishing in the top three.
- `平均名次`: lower is better.
- `名次方差`: ranking volatility.
- `场均领先`: champion progress margin contribution averaged across all races.
- `胜时领先`: average winner margin only among races won by that runner.

## Tests

```powershell
python -m unittest discover -s tests
```
