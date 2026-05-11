# Wuthering Waves Cubie Derby Monte Carlo

Python Monte Carlo simulator for Cubie Derby race outcomes. It ports the original MATLAB script into a reusable CLI and simulation module.

## Quick Start

Run a basic Season 1 simulation. In this project, cell `1` is the usual start cell and cell `0` is the finish cell.

```powershell
python cubie_derby.py --season 1 -n 100000 --start "1:*" --runners 3 4 8 10 --seed 42
```

Run with Season 2 rules. Season 2 uses a 32-position ring lap, special cells, and the reverse-moving NPC from round 3:

```powershell
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners 11 12 13 14 15 16 --seed 42
```

Print machine-readable output:

```powershell
python cubie_derby.py -n 10000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --json
```

For large Monte Carlo runs, enable CPU parallelism. Use `--workers 0` to use all CPU cores, or pass a fixed worker count such as `--workers 4`:

```powershell
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 42 --workers 0
```

## Parameter Guide

### `--season`

Select the ruleset.

- `--season 1`: Season 1 rules, default lap length `24`.
- `--season 2`: Season 2 rules, default lap length `32`, special cells enabled, NPC enabled from round 3.

Examples:

```powershell
python cubie_derby.py --season 1 -n 100000 --start "1:*" --runners 3 4 8 10 --seed 42
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners 11 12 13 14 15 16 --seed 42
```

### `--start`

Define the start grid. The ring cells are displayed as `0..23` in Season 1 and `0..31` in Season 2. By this project's naming convention, cell `1` is the usual start cell and cell `0` is the finish cell. Pre-start cells `-3..0` are also supported.

Common forms:

- `--start "1:*"`: all selected runners start together on cell `1`, with a fresh random left-to-right stack each simulated race.
- `--start "1:10;2:4,3;3:8"`: fixed custom layout.
- `--start "-3:10;-2:4,3;1:8"`: custom layout with pre-start cells.
- `--start "-3:2;-2:1,4;-1:3,6;1:5"`: custom Season 2-style layout.

Notes:

- `*` cannot be mixed with fixed cells in the same `--start` string.
- When `*` is used, `--runners` must also be provided.

Examples:

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:*" --runners 3 4 8 10 --seed 42
python cubie_derby.py -n 100000 --lap-length 24 --start "1:10;2:4,3;3:8" --runners 3 4 8 10 --seed 42
python cubie_derby.py --season 2 -n 100000 --start "-3:2;-2:1,4;-1:3,6;1:5" --runners 1 2 3 4 5 6 --seed 42
```

### `--runners`

Choose the participants. You can pass runner ids, runner names, or a random sample.

Common forms:

- `--runners 11 12 13 14 15 16`
- `--runners 今汐 长离 卡卡罗 守岸人`
- `--runners random`
- `--runners random:4`

Notes:

- `random` defaults to `6` unique runners from the current `1..20` pool.
- Random runner sampling also follows `--seed`.

Examples:

```powershell
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 42
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners random --seed 42 --workers 0
```

### `--initial-order`

Override the first-round action order only.

- If omitted and `--start "1:*"` is used, the first-round order follows the randomized left-to-right stack order.
- `--initial-order random`: reshuffle the first round independently from the stack order.
- `--initial-order start`: force the first round to follow the current grid order.
- `--initial-order 4,3,8,10`: fixed first-round order.

Examples:

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:*" --runners 3 4 8 10 --initial-order random
python cubie_derby.py -n 100000 --lap-length 24 --start "1:10;2:4,3;3:8" --runners 3 4 8 10 --initial-order start
```

### `--seed`

Make random behavior reproducible. This affects Monte Carlo runs, random start stacks, and `--runners random`.

Example:

```powershell
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners random --seed 42
```

### `--track-length` / `--lap-length`

Override the default lap length. This is mainly useful for custom experiments; otherwise, the default season length is used automatically.

Example:

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:*" --runners 3 4 8 10 --seed 42
```

### `--workers`

Enable CPU parallelism for large Monte Carlo runs.

- `--workers 0`: use all CPU cores.
- `--workers 4`: use a fixed worker count.

Example:

```powershell
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 42 --workers 0
```

### `--json`

Print machine-readable output instead of the formatted text table.

Example:

```powershell
python cubie_derby.py -n 10000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --json
```

### `--trace` / `--trace-log`

Trace a single race for debugging.

- `--trace`: print the traced race directly to the terminal.
- `--trace-log PATH`: write the traced race to a log file.

Examples:

```powershell
python cubie_derby.py --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 2 --trace
python cubie_derby.py --season 2 --trace-log logs/season2_trace.log --start "-3:2;-2:1,4;-1:3,6;1:5" --runners 1 2 3 4 5 6 --seed 42
```

### `--skill-ablation`

Run skill on/off ablation statistics. This first runs one all-skills-on baseline, then runs one additional simulation for each ablated runner.

Related options:

- `--skill-ablation-runners`: limit ablation to selected runners.
- `--skill-ablation-detail`: include the success-count distribution in the printed output.

Examples:

```powershell
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --skill-ablation --seed 42
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --skill-ablation --skill-ablation-runners 12 16 --skill-ablation-detail --seed 42
```

## Runner IDs

- `1` / `jinhsi`: 今汐
- `2` / `changli`: 长离
- `3` / `calcharo`: 卡卡罗
- `4` / `shorekeeper`: 守岸人. Uses a special `2..3` dice range; in skill ablation, disabling her skill changes her back to the normal `1..3` dice range.
- `5` / `camellya`: 椿
- `6` / `potato`: 小土豆
- `7` / `roccia`: 洛可可
- `8` / `brant`: 布兰特
- `9` / `cantarella`: 坎特蕾拉
- `10` / `zani`: 赞妮
- `11` / `cartethyia`: 卡提希娅
- `12` / `phoebe`: 菲比
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
- NPC is physically waiting on the finish cell `0` from race start, but it is not active for Hiyuki contact checks, action order, or ranking before round 3. It joins the action order from round 3, rolls with the selected runners, moves backward `1..6` positions on its own turn, and is always rightmost when sharing a cell. During its backward movement, if it passes through a cell while it still has movement remaining, it carries that cell's runners onward. At round end, NPC returns to `0` only when its position is less than the last-place runner's position.

## Output Columns

- `夺冠率`: estimated first-place probability.
- `晋级率`: estimated probability of finishing in the top four.
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
