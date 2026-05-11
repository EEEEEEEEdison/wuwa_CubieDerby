# Wuthering Waves Cubie Derby Monte Carlo

Python Monte Carlo simulator for Cubie Derby race outcomes. It ports the original MATLAB script into a reusable CLI and simulation module.

## Quick Start

Run a known custom start:

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:10;2:4,3;3:8" --runners 3 4 8 10 --seed 42
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
python cubie_derby.py -n 10000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --json
```

For large Monte Carlo runs, enable CPU parallelism. Use `--workers 0` to use all CPU cores, or pass a fixed worker count such as `--workers 4`:

```powershell
python cubie_derby.py -n 100000 --season 2 --start "0:*" --runners 11 12 13 14 15 16 --seed 42 --workers 0
```

Randomly sample runners from the current `1..20` runner pool. `--runners random` defaults to 6 unique runners; use `random:4` or another count to choose a different size. The choice is tied to `--seed`, so the same seed is reproducible.

```powershell
python cubie_derby.py -n 100000 --season 2 --start "0:*" --runners random --seed 42 --workers 0
```

Run skill ablation statistics. This first runs one all-skills-on baseline, then runs one additional simulation for each ablated runner. With 6 ablated runners and `-n 100000`, the total work is 7 groups, or 700,000 simulated races.

```powershell
python cubie_derby.py -n 100000 --season 2 --start "0:*" --runners 11 12 13 14 15 16 --skill-ablation --seed 42
```

Limit ablation to selected runners and include the detailed success-count distribution:

```powershell
python cubie_derby.py -n 100000 --season 2 --start "0:*" --runners 11 12 13 14 15 16 --skill-ablation --skill-ablation-runners 12 16 --skill-ablation-detail --seed 42
```

Trace one race for rule debugging. Trace output is formatted for reading: each action is separated by blank lines, and skill/special-cell checks are marked with `判定时机` labels.

```powershell
python cubie_derby.py --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 2 --trace
```

Write one fully traced race to a log file. This is useful for checking Season 2 special cells and NPC movement without running a full Monte Carlo batch:

```powershell
python cubie_derby.py --season 2 --trace-log logs/season2_trace.log --start "-3:2;-2:1,4;-1:3,6;0:5" --runners 1 2 3 4 5 6 --seed 42
```

Use `--season 2` to apply the Season 2 ruleset to a custom start. Without `--lap-length`, Season 2 defaults to a 32-position ring lap.

## Runner IDs

- `4` / `shorekeeper`: 守岸人. Uses a special `2..3` dice range; in skill ablation, disabling her skill changes her back to the normal `1..3` dice range.
- `13` / `sigrika`: 西格莉卡. At round start, marks up to two immediately higher-ranked runners; marked runners move 1 fewer step that round, with a minimum movement of 1. She can act in round 1 for fixed starts, but skips round 1 for random stack starts such as `--start "1:*"`.
- `14` / `luuk_herssen`: 陆赫斯. Only on his own turn, forward special cells move his active group 4 cells total; backward special cells move his active group 2 cells backward.
- `15` / `denia`: 达尼娅. If her dice roll matches her previous round's dice roll, she gets +2 steps.
- `16` / `hiyuki`: 绯雪. After her movement path and the NPC intersect once, including passing through or landing on the NPC's cell, she gains a +1 step bonus for future moves. NPC movement paths are checked the same way, but the bonus does not stack.
- `17` / `chisa`: 千咲. Dice are rolled for all round participants at round start; if her dice value is tied for the lowest value, including NPC when active, she gets +2 steps that turn.
- `18` / `mornye`: 莫宁. Her dice follows a deterministic `3 -> 2 -> 1` cycle.
- `19` / `lynae`: 琳奈. Before Sigrika's debuff is applied, she has a 60% chance to move with double dice, a 20% chance to be unable to move, and otherwise moves normally.
- `20` / `aemeath`: 爱弥斯. Once per race, when a moving group containing Aemeath passes cell `17` in either direction and another non-NPC runner is ahead of cell `17`, only Aemeath teleports to the nearest such runner's cell and enters from the left. If another runner carries her, the original moving group removes Aemeath and continues its movement. If Aemeath is the active runner while carrying others, the carried runners stop on cell `17`, and Aemeath continues any remaining movement after teleporting. If no valid target exists, the skill is not consumed.

## Season 2 Rules

- Forward cells: `3`, `11`, `16`, `23`.
- Backward cells: `10`, `28`.
- Shuffle cells: `6`, `20`.
- NPC is physically waiting at position `0` from race start, but it is not active for Hiyuki contact checks, action order, or ranking before round 3. It joins the action order from round 3, rolls with the selected runners, moves backward `1..6` positions on its own turn, and is always rightmost when sharing a cell. During its backward movement, if it passes through a cell while it still has movement remaining, it carries that cell's runners onward. At round end, NPC returns to `0` only when its position is less than the last-place runner's position.

## Output Columns

- `夺冠率`: estimated first-place probability.
- `前三率`: estimated probability of finishing in the top three.
- `平均名次`: lower is better.
- `名次方差`: ranking volatility.
- `场均领先`: champion progress margin contribution averaged across all races.
- `胜时领先`: average winner margin only among races won by that runner.

When `--skill-ablation` is enabled, an extra table is printed:

- `开启胜率`: that runner's win rate in the all-skills-on baseline.
- `关闭胜率`: that runner's win rate when only that runner's skill is disabled.
- `净胜率`: `开启胜率 - 关闭胜率`.
- `平均成功次数`: average successful skill activations per baseline race.
- `单次边际胜率`: descriptive linear estimate of win-rate change per additional successful activation; `无数据` means the activation count did not vary.

## Tests

```powershell
python -m unittest discover -s tests
```
