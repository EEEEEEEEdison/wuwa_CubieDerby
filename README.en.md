# Wuthering Waves Cubie Derby Monte Carlo

<p align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/语言-中文-red" alt="Chinese" /></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/Language-English-blue" alt="English" /></a>
</p>

Python Monte Carlo simulator for Cubie Derby race outcomes.

Core things this project can simulate:

- Season 1 and Season 2 race rules.
- Custom runner lineups and runner counts.
- Full season-roster combination scans for a fixed field size.
- Custom start layouts, including pre-start cells and random same-cell stacks.
- Runner skills, Season 2 special cells, and the reverse-moving NPC.
- Monte Carlo win-rate statistics, skill ablation, and single-race trace logs.

## Quick Start

Run a basic Season 1 simulation. In this project, cell `1` is the usual start cell and cell `0` is the finish cell.

```powershell
python cubie_derby.py --season 1 -n 100000 --start "1:*" --runners 3 4 8 10
```

Run with Season 2 rules. Season 2 uses a 32-position ring lap, special cells, and the reverse-moving NPC from round 3:

```powershell
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners 11 12 13 14 15 16
```

`--runners` selects the participants. You can freely change both the runner combination and the number of participants; see [Runner IDs and Skills](#runner-ids-and-skills) for the available ids, names, and skill notes.

## Parameter Guide

### `-n` / `--iterations`

Set how many simulated races to run. Larger values give more stable Monte Carlo estimates, but take longer to finish.

When `--season-roster-scan` is enabled, `-n` means races per combination, not total races. For example, Season 2 has `15` runners in its actual roster, so a 6-runner scan uses `C(15, 6) = 5005` combinations. With `-n 10`, the total workload is `5005 * 10 = 50050` races.

Example:

```powershell
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners 11 12 13 14 15 16
```

### `--season`

Select the ruleset.

- `--season 1`: Season 1 rules, default lap length `24`.
- `--season 2`: Season 2 rules, default lap length `32`, special cells enabled, NPC enabled from round 3.

Examples:

```powershell
python cubie_derby.py --season 1 -n 100000 --start "1:*" --runners 3 4 8 10 --seed 42
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners 11 12 13 14 15 16 --seed 42
```

### `--season-roster-scan`

Enumerate every same-size combination from the selected season roster, run the simulator for each combination, and then aggregate the normal summary metrics back onto each runner.

This is useful when you want answers such as "in Season 2 six-runner matches, who has the highest overall win rate across all possible lineups?".

Notes:

- Do not combine this mode with `--runners`; the season roster is chosen automatically from `--season`.
- The current Season 1 scan pool is runners `1..12`.
- The current Season 2 scan pool is `1, 2, 3, 4, 6, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20`.
- The printed table is aggregated per runner across every combination they appear in.
- `--trace` and `--skill-ablation` are not used in this mode.

Example:

```powershell
python cubie_derby.py --season 2 --season-roster-scan --field-size 6 -n 10000 --start "1:*" --workers 0
```

### `--field-size`

Used together with `--season-roster-scan`. It sets the number of runners in each enumerated combination.

Examples:

- `--field-size 6`: scan all 6-runner combinations in the chosen season roster.
- `--field-size 4`: scan all 4-runner combinations in the chosen season roster.

### `--start`

Define the start grid. The ring cells are displayed as `0..23` in Season 1 and `0..31` in Season 2. By this project's naming convention, cell `1` is the usual start cell and cell `0` is the finish cell. Pre-start cells `-3..0` are also supported.

Common forms:

- `--start "1:*"`: all selected runners start together on cell `1`, with a fresh random left-to-right stack each simulated race. This is a good fit for scenarios such as the upper half of group-stage matches.
- `--start "-3:2;-2:1,4;-1:3,6;1:5"`: custom layout with pre-start cells. This is a good fit for scenarios such as the lower half of group-stage matches with preset starting positions.

Notes:

- `*` cannot be mixed with fixed cells in the same `--start` string.
- In normal simulation mode, when `*` is used, `--runners` must also be provided.
- When `--season-roster-scan` is used, `--start` must be a reusable `*` form such as `--start "1:*"` or `--start "-1:*"`.
- Within the same cell, runners are ordered from left to right, and the runner on the left ranks higher.
- `--start "-3:2;-2:1,4;-1:3,6;1:5"` means: runner `2` starts on `-3`; runners `1` and `4` start together on `-2` from left to right; runners `3` and `6` start together on `-1` from left to right; runner `5` starts alone on cell `1`.

Examples:

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:*" --runners 3 4 8 10 --seed 42
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
- In `--season-roster-scan` mode, only `random` and `start` are supported, because fixed runner-id orders are not reusable across all combinations.

Examples:

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:*" --runners 3 4 8 10 --initial-order random
python cubie_derby.py -n 100000 --lap-length 24 --start "1:10;2:4,3;3:8" --runners 3 4 8 10 --initial-order start
```

### `--seed`

Make random behavior reproducible. This affects Monte Carlo runs, random start stacks, `--runners random`, and season-roster scans when you want to rerun the same full traversal.

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
- In normal simulation mode, this parallelizes race batches within one lineup.
- In `--season-roster-scan` mode, this parallelizes across different lineup combinations.

Example:

```powershell
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 42 --workers 0
```

### `--json`

Print machine-readable output instead of the formatted text table. In `--season-roster-scan` mode, the JSON output contains the aggregated scan result rather than a single-lineup summary.

Example:

```powershell
python cubie_derby.py -n 10000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --json
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

## Debugging

### `--trace`

Trace a single race directly in the terminal. This is useful when you want to inspect action order, skill timing, NPC movement, special-cell effects, or final ranking resolution step by step.

Example:

```powershell
python cubie_derby.py --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 2 --trace
```

### `--trace-log`

Write one traced race to a log file instead of only printing it to the terminal. This is useful when you want to save a full readable process log for later checking or sharing.

Example:

```powershell
python cubie_derby.py --season 2 --trace-log logs/season2_trace.log --start "-3:2;-2:1,4;-1:3,6;1:5" --runners 1 2 3 4 5 6 --seed 42
```

## Runner IDs and Skills

The notes below describe the current simulator implementation.

Season grouping in this project's numbering scheme:

- Season 1 roster: `1 今汐`, `2 长离`, `3 卡卡罗`, `4 守岸人`, `5 椿`, `6 小土豆`, `7 洛可可`, `8 布兰特`, `9 坎特蕾拉`, `10 赞妮`, `11 卡提希娅`, `12 菲比`
- Season 2 roster: `1 今汐`, `2 长离`, `3 卡卡罗`, `4 守岸人`, `6 小土豆`, `11 卡提希娅`, `12 菲比`, `13 西格莉卡`, `14 陆赫斯`, `15 达尼娅`, `16 绯雪`, `17 千咲`, `18 莫宁`, `19 琳奈`, `20 爱弥斯`

So in the actual Season 2 competition pool, runners `5 椿`, `7 洛可可`, `8 布兰特`, `9 坎特蕾拉`, and `10 赞妮` are not included.

`--season` switches the race ruleset, not the allowed runner list, so you can still choose any custom runner mix in `--runners` when you want custom experiments.

- `1` / `jinhsi`: 今汐. After another non-NPC runner finishes their action, if that runner ends in 今汐's cell and is positioned to her left, 今汐 makes a `40%` check; on success, she moves to the far left of that cell.
- `2` / `changli`: 长离. At round end, if she is not the rightmost runner in her current cell, she makes a `65%` check; on success, she is forced to act last next round.
- `3` / `calcharo`: 卡卡罗. At action start, if he is currently last place, he gets `+3` steps.
- `4` / `shorekeeper`: 守岸人. Uses a special `2..3` dice range instead of the normal `1..3`.
- `5` / `camellya`: 椿. At action start, she makes a `50%` check to move alone; on success, she does not carry other runners this turn and gains extra steps equal to the number of other runners in her current cell.
- `6` / `potato`: 小土豆. After rolling, makes a `28%` check to repeat the same die and add it again.
- `7` / `roccia`: 洛可可. If she is the last actor of the round, she gets `+2` steps.
- `8` / `brant`: 布兰特. If he is the first actor of the round, he gets `+2` steps.
- `9` / `cantarella`: 坎特蕾拉. Starts in step-by-step movement mode. While this mode is active, she moves one cell at a time; if she reaches a cell with other runners, she merges with that cell for the remaining movement and then leaves that special mode afterward.
- `10` / `zani`: 赞妮. Uses a special `1 or 3` dice. At action start, if she shares a cell with others, she makes a `40%` check; on success, her next action is stored with an extra `+2` steps.
- `11` / `cartethyia`: 卡提希娅. Once per race, after her own action ends, if she is last place, she enters an empowered state. For the rest of the race, each of her later turns makes a `60%` check for `+2` steps.
- `12` / `phoebe`: 菲比. At action start, makes a `50%` check for `+1` step.
- `13` / `sigrika`: 西格莉卡. At round start, marks up to two immediately higher-ranked runners; marked runners move `1` fewer step that round, with a minimum movement of `1`. She can act in round `1` for fixed starts, but skips round `1` for random stack starts such as `--start "1:*"`.
- `14` / `luuk_herssen`: 陆赫斯. Only on his own turn, forward special cells move his active group `4` cells total, and backward special cells move his active group `2` cells backward.
- `15` / `denia`: 达尼娅. If her current dice roll matches her previous round's dice roll, she gets `+2` steps.
- `16` / `hiyuki`: 绯雪. After round `3`, once her movement path and the active NPC path intersect, she gains a persistent `+1` step bonus for future moves. The bonus does not stack.
- `17` / `chisa`: 千咲. Dice are rolled for all round participants at round start; if her dice value is tied for the lowest value, including NPC when active, she gets `+2` steps that turn.
- `18` / `mornye`: 莫宁. Her dice follows a deterministic `3 -> 2 -> 1` cycle.
- `19` / `lynae`: 琳奈. Before Sigrika's debuff is applied, she has a `60%` chance to move with double dice, a `20%` chance to be unable to move, and otherwise moves normally.
- `20` / `aemeath`: 爱弥斯. Once per race, after she has passed cell `17`, her skill enters a pending state. Passing cell `17` while being carried by another runner also arms this pending state, but does not trigger an immediate check. At the end of each of 爱弥斯's own forward moves, if the pending state is armed, she checks whether another non-NPC runner is ahead of her current position. If so, only 爱弥斯 teleports to the nearest such runner's cell and enters from the left; any runners she carried stay on her action's normal landing cell. If no valid target exists, the pending state remains and she checks again after her next own forward move.

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
