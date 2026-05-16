# Wuthering Waves Cubie Derby Monte Carlo

<p align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/语言-中文-red" alt="Chinese" /></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/Language-English-blue" alt="English" /></a>
</p>

这是一个用于模拟团子赛跑结果的 Python 蒙特卡洛工具。

这个项目当前可以模拟的核心内容包括：

- 第 1 季和第 2 季的赛道规则。
- 自定义参赛角色组合和参赛人数。
- 固定人数下，对整季角色池做全组合遍历统计。
- 自定义起始站位，包括负格预起跑区和同格随机堆叠。
- 角色技能、第 2 季特殊格、以及反向移动的 NPC。
- 胜率统计、技能消融统计，以及单局逐过程 trace 日志。

## 快速开始

运行一个基础的第 1 季模拟。在本项目的命名习惯中，第 `1` 格通常视为起点，第 `0` 格视为终点。

```powershell
python cubie_derby.py --season 1 -n 100000 --start "1:*" --runners 3 4 8 10
```

运行第 2 季规则。第 2 季使用 32 格环形赛道，包含特殊格，并会在第 3 回合引入反向移动 NPC：

```powershell
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners 11 12 13 14 15 16
```

如果你想让程序按某个比赛阶段的默认规则自动补齐参数，可以直接传 `--match-type`：

```powershell
python cubie_derby.py --season 2 --match-type group-round-1 -n 100000 --runners 11 12 13 14 15 16 --seed 42
```

如果你想直接跑完整个赛季 2 赛事流程，可以改用 `--champion-prediction`：

```powershell
python cubie_derby.py --season 2 --champion-prediction random --seed 42
```

如果你想一步一步引导输入，现在直接运行 `python cubie_derby.py` 就会进入向导。你也可以带上部分启动参数，让向导只补剩下缺的信息。如果你想用英文提示，可以再加上 `--interactive-language en`：

```powershell
python cubie_derby.py
python cubie_derby.py --interactive --season 2
python cubie_derby.py --season 2 --iterations 10000 --json
python cubie_derby.py --interactive --interactive-language en --season 2 --json
```

`--runners` 用于选择参赛角色。你可以自由更改角色组合和参赛人数；可用编号、名称和技能说明见下方的[角色编号与技能](#角色编号与技能)。

## 参数说明

### `-n` / `--iterations`

设置模拟局数。数值越大，蒙特卡洛结果越稳定，但运行时间也越长。

当启用 `--season-roster-scan` 时，`-n` 表示“每个组合跑多少局”，而不是总局数。比如第 2 季当前实际角色池有 `18` 名角色，做 6 人局全组合扫描时，一共有 `C(18, 6) = 18564` 个组合。若 `-n 10`，总模拟量就是 `18564 * 10 = 185640` 局。

示例：

```powershell
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners 11 12 13 14 15 16
```

### `--season`

选择赛季规则。

- `--season 1`：第 1 季规则，默认圈长 `24`。
- `--season 2`：第 2 季规则，默认圈长 `32`，启用特殊格，并从第 3 回合开始启用 NPC。

示例：

```powershell
python cubie_derby.py --season 1 -n 100000 --start "1:*" --runners 3 4 8 10 --seed 42
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners 11 12 13 14 15 16 --seed 42
```

### `--match-type`

按内置比赛阶段规则自动补齐参数。当前这套能力先支持第 2 季，阶段键包括：

- `group-round-1`
- `group-round-2`
- `elimination`
- `losers-bracket`
- `winners-bracket`
- `grand-final`

说明：

- 也支持中文别名，例如 `小组赛第一轮`、`总决赛`。
- `group-round-1` 会自动使用 `--start "1:*"`，且不显示晋级统计。
- `group-round-2` 会把 `--runners` 的顺序视为上一轮排名，并自动生成 `0 / -1 / -2 / -3` 的站位。
- `elimination`、`losers-bracket`、`winners-bracket` 都会自动使用 `--start "1:*"`，默认取前三晋级。
- `grand-final` 会自动使用 `--start "1:*"`，只统计夺冠率，不显示晋级率。
- 在单阶段模式下，你仍然可以手动传 `--start` 覆盖默认站位。

示例：

```powershell
python cubie_derby.py --season 2 --match-type group-round-2 -n 100000 --runners 11 12 13 14 15 16 --seed 42
python cubie_derby.py --season 2 --match-type grand-final -n 100000 --runners 11 12 13 14 15 16 --seed 42
```

### `--champion-prediction`

直接运行整届赛事，而不是只跑单个阶段。

- `--champion-prediction random`：跑 1 届完整赛事，输出每个阶段的排名与晋级结果，以及最终冠军。
- `--champion-prediction monte-carlo`：重复跑很多届完整赛事，并汇总角色夺冠率。

当前赛季 2 的整届流程是：

- 18 名角色先随机分成 3 个 6 人小组。
- 每组先跑 `group-round-1`，再按上一轮排名跑 `group-round-2`。
- 每组第二轮前 4 名晋级，共 12 人。
- 12 人再随机分成 2 个 6 人淘汰赛组。
- 每组淘汰赛前 3 名进入胜者组，后 3 名进入败者组第一轮。
- 胜者组前 3 名直通总决赛。
- 胜者组后 3 名与败者组第一轮前 3 名进入败者组第二轮。
- 败者组第二轮前 3 名进入总决赛。

示例：

```powershell
python cubie_derby.py --season 2 --champion-prediction random --seed 42
python cubie_derby.py --season 2 --champion-prediction monte-carlo -n 10000 --seed 42 --workers 0
```

### `--interactive`

进入交互式向导。现在会先按“分析大类 -> 子模式”递进提问：

- 赛事冠军预测：先选是“单届演示”还是 “Monte Carlo 统计”，再选择从哪个赛事阶段开始，并补齐继续推演到总决赛所需的最少信息。
- 单场胜率分析：先进入单场分析分支，再选择当前比赛阶段、登场角色、起跑配置、模拟次数等参数。

说明：

- 当前交互式冠军预测支持从赛季 2 的任意赛事入口开始，例如 `小组A第二轮`、`淘汰赛A`、`胜者组`、`总决赛`。
- 对很多中途入口，向导支持“输入完整排名后自动推导后续名单”，减少手工拆分。
- 交互提示会先说明“当前起始阶段”和“后续将依次模拟哪些阶段”，再开始提问。
- 如果你直接运行 `python cubie_derby.py`，向导会自动进入交互模式，并默认使用第 2 季；你也可以先带上 `--season`、`--iterations`、`--json` 等参数，再由向导补齐剩余输入。
- `--interactive-language en` 会把交互向导提示切到英文，便于英文环境演示或录屏；JSON 结构不变。

示例：

```powershell
python cubie_derby.py --interactive --season 2
python cubie_derby.py --interactive --season 2 --champion-prediction monte-carlo --json
```

### `--tournament-context-in` / `--tournament-context-out`

为交互式冠军预测保存或载入赛事上下文，适合把“从某个中途阶段开始的补录输入”保存下来反复复用。

- `--tournament-context-out PATH`：把本次交互收集好的赛事入口上下文写到 JSON 文件。
- `--tournament-context-in PATH`：直接从已有 JSON 文件载入赛事入口上下文，再继续做单届或 Monte Carlo 冠军预测。

示例：

```powershell
python cubie_derby.py --interactive --season 2 --champion-prediction random --tournament-context-out saved_context.json
python cubie_derby.py --champion-prediction monte-carlo -n 10000 --workers 0 --tournament-context-in saved_context.json --json
```

### `--season-roster-scan`

对所选赛季的角色池做“同人数全组合遍历”，每个组合都跑模拟，然后再把常规统计指标汇总回每名角色身上。

这个模式适合回答类似这样的问题：“在第 2 季六人局里，跨越所有可能阵容后，谁的综合胜率最高？”

说明：

- 该模式不要和 `--runners` 一起使用；角色池会根据 `--season` 自动选择。
- 当前第 1 季扫描池是 `1..12`。
- 当前第 2 季扫描池是 `1, 2, 3, 4, 6, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20`。
- 输出表会按角色汇总其出现在所有组合中的整体表现。
- 该模式下不会使用 `--trace` 和 `--skill-ablation`。

示例：

```powershell
python cubie_derby.py --season 2 --season-roster-scan --field-size 6 -n 10000 --start "1:*" --workers 0
```

### `--field-size`

与 `--season-roster-scan` 配合使用，用于指定每个组合里包含多少名参赛角色。

示例：

- `--field-size 6`：扫描该赛季角色池中的全部 6 人组合。
- `--field-size 4`：扫描该赛季角色池中的全部 4 人组合。

### `--start`

定义起始站位。第 1 季显示格为 `0..23`，第 2 季显示格为 `0..31`。按本项目的命名习惯，第 `1` 格通常视为起点，第 `0` 格视为终点。也支持 `-3..0` 的预起跑格。

常见写法：

- `--start "1:*"`：所有参赛角色都从第 `1` 格同格出发，每一局都会重新随机生成从左到右的堆叠顺序。这个写法很适合小组赛上半这种统一起点场景。
- `--start "-3:2;-2:1,4;-1:3,6;1:5"`：带有预起跑格的自定义站位。这个写法很适合小组赛下半这种存在固定初始站位的场景。

说明：

- `*` 不能和固定格写法混在同一个 `--start` 字符串里。
- 普通模拟模式下，如果用了 `*`，则必须同时提供 `--runners`。
- `--season-roster-scan` 模式下，`--start` 必须是可复用的 `*` 形式，例如 `--start "1:*"` 或 `--start "-1:*"`。
- 同一格内角色的顺序是从左到右，越靠左排名越高。
- `--start "-3:2;-2:1,4;-1:3,6;1:5"` 的实际含义是：`2` 号角色起始在 `-3` 格；`1` 和 `4` 号角色一起从 `-2` 格出发，顺序从左到右；`3` 和 `6` 号角色一起从 `-1` 格出发，顺序从左到右；`5` 号角色单独从第 `1` 格出发。

示例：

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:*" --runners 3 4 8 10 --seed 42
python cubie_derby.py --season 2 -n 100000 --start "-3:2;-2:1,4;-1:3,6;1:5" --runners 1 2 3 4 5 6 --seed 42
```

### `--runners`

选择参赛角色。你可以传角色编号、角色名称，或让程序随机抽样。

常见写法：

- `--runners 11 12 13 14 15 16`
- `--runners 今汐 长离 卡卡罗 守岸人`
- `--runners random`
- `--runners random:4`

说明：

- `random` 默认会从当前 `1..20` 编号池中随机抽取 `6` 个不重复角色。
- 角色随机抽样同样会受到 `--seed` 影响。

示例：

```powershell
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 42
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners random --seed 42 --workers 0
```

### `--initial-order`

只覆盖第一回合的行动顺序。

- 若不填写，并且使用的是 `--start "1:*"`，则第一回合默认按该局随机堆叠后的从左到右顺序行动。
- `--initial-order random`：第一回合行动顺序与堆叠顺序独立，单独再随机一次。
- `--initial-order start`：强制第一回合按当前棋盘顺序行动。
- `--initial-order 4,3,8,10`：指定固定的第一回合行动顺序。
- 在 `--season-roster-scan` 模式里，只支持 `random` 和 `start`，因为固定角色编号顺序无法复用于全部组合。

示例：

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:*" --runners 3 4 8 10 --initial-order random
python cubie_derby.py -n 100000 --lap-length 24 --start "1:10;2:4,3;3:8" --runners 3 4 8 10 --initial-order start
```

### `--seed`

用于让随机过程可复现。它会影响蒙特卡洛模拟、随机起始堆叠、`--runners random`，以及 `--season-roster-scan` 模式下的整套遍历结果。

示例：

```powershell
python cubie_derby.py --season 2 -n 100000 --start "1:*" --runners random --seed 42
```

### `--track-length` / `--lap-length`

覆盖默认圈长。这个参数主要用于做自定义实验；如果只是按赛季规则模拟，一般直接使用赛季默认值即可。

示例：

```powershell
python cubie_derby.py -n 100000 --lap-length 24 --start "1:*" --runners 3 4 8 10 --seed 42
```

### `--workers`

为大规模蒙特卡洛模拟启用 CPU 并行。

- `--workers 0`：使用全部 CPU 核心。
- `--workers 4`：固定使用 4 个 worker。
- 普通模拟模式下，它会把同一阵容的模拟批次拆开并行。
- `--season-roster-scan` 模式下，它会把不同组合拆开并行。

示例：

```powershell
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 42 --workers 0
```

### `--json`

输出机器可读的 JSON，而不是格式化文本表格。在 `--season-roster-scan` 模式下，JSON 输出的是整套组合扫描的汇总结果，而不是单一阵容结果。

示例：

```powershell
python cubie_derby.py -n 10000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --json
```

### `--skill-ablation`

运行技能开关消融统计。它会先跑一组“全技能开启”的基准模拟，再对每名被评估角色分别跑一组“仅关闭该角色技能”的额外模拟。

相关参数：

- `--skill-ablation-runners`：只评估指定角色。
- `--skill-ablation-detail`：在输出里追加技能成功次数分布。

示例：

```powershell
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --skill-ablation --seed 42
python cubie_derby.py -n 100000 --season 2 --start "1:*" --runners 11 12 13 14 15 16 --skill-ablation --skill-ablation-runners 12 16 --skill-ablation-detail --seed 42
```

## 调试

### `--trace`

直接在终端输出单局比赛的逐过程日志。适合用来核对行动顺序、技能触发时机、NPC 路径、特殊格效果以及最终排名判定。

示例：

```powershell
python cubie_derby.py --season 2 --start "1:*" --runners 11 12 13 14 15 16 --seed 2 --trace
```

### `--trace-log`

将单局 trace 日志写入文件，而不只是打印到终端。适合把一整局的详细过程保存下来，后续复盘或分享。

示例：

```powershell
python cubie_derby.py --season 2 --trace-log logs/season2_trace.log --start "-3:2;-2:1,4;-1:3,6;1:5" --runners 1 2 3 4 5 6 --seed 42
```

## 角色编号与技能

以下说明描述的是当前模拟器中的实现逻辑。

按本项目编号体系划分的赛季角色池如下：

- 第 1 季角色池：`1 今汐`、`2 长离`、`3 卡卡罗`、`4 守岸人`、`5 椿`、`6 小土豆`、`7 洛可可`、`8 布兰特`、`9 坎特蕾拉`、`10 赞妮`、`11 卡提希娅`、`12 菲比`
- 第 2 季角色池：`1 今汐`、`2 长离`、`3 卡卡罗`、`4 守岸人`、`6 小土豆`、`11 卡提希娅`、`12 菲比`、`13 西格莉卡`、`14 陆赫斯`、`15 达尼娅`、`16 绯雪`、`17 千咲`、`18 莫宁`、`19 琳奈`、`20 爱弥斯`、`21 奥古斯塔`、`22 尤诺`、`23 弗洛洛`

因此，在实际的第 2 季比赛角色池中，不包含 `5 椿`、`7 洛可可`、`8 布兰特`、`9 坎特蕾拉`、`10 赞妮`。

`--season` 切换的是赛道规则，不是角色选择限制，所以若你想做自定义实验，仍然可以在 `--runners` 中自由混搭角色。

- `1` / `jinhsi`：今汐。只有其他非 NPC 角色在自己的回合中完成行动结算后，若该行动角色与今汐同格，且紧邻位于今汐左侧，今汐才会进行一次 `40%` 判定；成功后移动到该格最左侧。这个判定看“该回合行动结算后的最终站位”，因此普通移动、无法行动视为主动移动 `0` 格，以及落在打乱格后被重新排序，都可能让今汐满足条件。NPC 行动和尤诺后续的汇集效果不会触发今汐。
- `2` / `changli`：长离。回合结束时，若她不是自己所在格的最右侧角色，则进行一次 `65%` 判定；成功后，下一回合强制最后行动。
- `3` / `calcharo`：卡卡罗。行动开始时，若当前处于最后一名，则额外 `+3` 步。
- `4` / `shorekeeper`：守岸人。骰子范围不是普通的 `1..3`，而是特殊的 `2..3`。
- `5` / `camellya`：椿。行动开始时，进行一次 `50%` 判定决定是否独自行动；成功后，本回合不再携带同格角色，并获得等于当前格其他角色数量的额外步数。
- `6` / `potato`：小土豆。投骰结束后，进行一次 `28%` 判定；成功则重复本次骰子，并将同样点数再加一次。
- `7` / `roccia`：洛可可。若本回合最后行动，则额外 `+2` 步。
- `8` / `brant`：布兰特。若本回合最先行动，则额外 `+2` 步。
- `9` / `cantarella`：坎特蕾拉。初始处于逐格移动模式。该模式下，她会一格一格地前进；若中途到达存在其他角色的格子，则会在该格合流，并带着该格角色继续完成剩余移动，随后退出该特殊模式。
- `10` / `zani`：赞妮。使用特殊骰子，只会掷出 `1` 或 `3`。行动开始时，若与其他角色同格，则进行一次 `40%` 判定；成功后，为下一次行动存储一个 `+2` 步加成。
- `11` / `cartethyia`：卡提希娅。每场比赛最多 1 次。自身行动结束后，若她处于最后一名，则进入强化状态。之后比赛剩余回合中，她每次行动都会进行一次 `60%` 判定；成功则额外 `+2` 步。
- `12` / `phoebe`：菲比。行动开始时，进行一次 `50%` 判定；成功则额外 `+1` 步。
- `13` / `sigrika`：西格莉卡。每回合开始时，标记排名紧邻且高于自己的至多两名角色；被标记角色本回合少走 `1` 步，但最少仍会移动 `1` 步。若是固定开局站位，则西格莉卡第一回合可以发动；若是 `--start "1:*"` 这种随机同格开局，则第一回合不发动。
- `14` / `luuk_herssen`：陆赫斯。只在自己的回合生效。若到达前进特殊格，则其本回合移动队列总共前进 `4` 格；若到达后退特殊格，则其本回合移动队列总共后退 `2` 格。
- `15` / `denia`：达尼娅。若本回合骰子点数与上一回合骰子点数相同，则额外 `+2` 步。
- `16` / `hiyuki`：绯雪。第 3 回合后，一旦她的移动路径与已激活 NPC 的路径发生接触，就获得一个持续存在的 `+1` 步加成。该加成不叠加。
- `17` / `chisa`：千咲。每回合开始时，会先为全部行动参与者统一掷骰；若她的骰子点数是全场最小值之一，则本回合额外 `+2` 步。NPC 激活后也会参与这个“最小点数”判定。
- `18` / `mornye`：莫宁。她的骰子固定按 `3 -> 2 -> 1` 循环。
- `19` / `lynae`：琳奈。在西格莉卡减速生效前，她有 `60%` 概率以双倍骰子移动，有 `20%` 概率本回合无法行动，其余情况下正常移动。
- `20` / `aemeath`：爱弥斯。每场比赛最多 1 次。只要她已经经过第 `17` 格，技能就会进入待判定状态。即便是被其他角色带着经过第 `17` 格，也只会进入待判定状态，不会立刻发动。之后，在爱弥斯每次自身主动前进结束时，若待判定状态已开启，则会检查自己前方是否存在其他非 NPC 角色；若存在，则只有爱弥斯自己会传送到最近目标所在格，并从该格最左侧加入；若她本回合带着其他角色移动，则那些被她带着的角色仍留在她原本行动的正常落点。若当前没有可传送目标，则待判定状态保留，等待她下一次自身主动前进结束后继续检查。
- `21` / `augusta`：奥古斯塔。行动开始时，若自己位于同格最左侧，且同格存在其他非 NPC 角色，则本回合不行动；同时下一回合固定最后行动，并且该回合不再判定自身技能。若是 `--start "1:*"` 这种随机同格开局，则第一回合不发动；若是固定自定义站位，则第一回合照常判定。
- `22` / `luno`：尤诺。每场比赛最多 1 次，且只会在自己主动行动结束后判定。若此时自己已经经过第 `17` 格，并且去掉 NPC 后当前排名既不是第一名也不是最后一名，则将所有非 NPC 角色汇集到自己所在格，格内顺序按发动前的当前排名从高到低排列。若不满足该条件，则保留技能，等下次主动行动结束后继续判定。
- `23` / `phrolova`：弗洛洛。行动开始时，若自己位于同格最右侧，且同格存在其他非 NPC 角色，则本回合额外前进 `3` 格。若是 `--start "1:*"` 这种随机同格开局，则第一回合不发动；若是固定自定义站位，则第一回合照常判定。

## 第 2 季赛道规则

- 前进格：`3`、`11`、`16`、`23`
- 后退格：`10`、`28`
- 打乱格：`6`、`20`
- NPC 从比赛开始起就物理存在于终点格 `0`，但在第 3 回合前，它不会参与绯雪接触判定、行动顺序和排名。第 3 回合开始后，NPC 会加入行动顺序，与其他角色一起掷点，在自己的回合反向移动 `1..6` 格，并且在同格时永远处于最右侧。NPC 反向移动过程中，只要经过某格时自己还有剩余步数，就会带着该格角色继续后退。每轮结束时，只有当 NPC 的位置小于最后一名角色的位置时，NPC 才会被送回第 `0` 格。

## 输出列说明

- `夺冠率`：估计的一名概率。
- `晋级率`：估计的前 N 名概率，N 可通过 `--qualify-cutoff` 控制，默认是前四名。
- `平均名次`：越低越好。
- `名次方差`：名次波动程度。
- `场均领先`：按全部对局平均后的冠军领先贡献。
- `胜时领先`：只在该角色获胜的对局中统计平均领先距离。

启用 `--skill-ablation` 后，还会额外打印一张技能消融表：

- `开启胜率`：全技能开启基准组中，该角色的胜率。
- `关闭胜率`：仅关闭该角色技能时，该角色的胜率。
- `净胜率`：`开启胜率 - 关闭胜率`。
- `平均成功次数`：全技能开启基准组中，该角色每局平均成功发动技能的次数。
- `单次边际胜率`：对“每多成功发动 1 次技能，大约带来多少胜率变化”的描述性线性估计；若显示 `无数据`，说明成功次数没有波动。

## 测试

```powershell
python -m unittest discover -s tests
```
