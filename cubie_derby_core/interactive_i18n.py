from __future__ import annotations

from functools import lru_cache


INTERACTIVE_LANGUAGE_CHOICES = ("zh", "en")


TRANSLATIONS_EN: dict[str, str] = {
    "请选择分析大类": "Choose analysis branch",
    "请选择赛季": "Choose season",
    "第1季": "Season 1",
    "第2季": "Season 2",
    "赛事冠军预测": "Tournament champion prediction",
    "单场胜率分析": "Single-stage win-rate analysis",
    "你正在进入“单场胜率分析”；下一步会先选择具体比赛阶段。": (
        "You are entering single-stage win-rate analysis. Next you will choose the specific match stage."
    ),
    "你正在进入“赛事冠军预测”；下一步会选择单届演示或 Monte Carlo 统计。": (
        "You are entering tournament champion prediction. Next you will choose a single-run demo or Monte Carlo statistics."
    ),
    "当前第1季交互向导先提供单场胜率分析；赛事冠军预测将在后续版本开放。": (
        "Season 1 currently offers the single-stage analysis wizard first. Tournament champion prediction will open in a later version."
    ),
    "请选择冠军预测方式": "Choose champion prediction mode",
    "请选择数据分析深度": "Choose data analysis depth",
    "请选择冠军预测入口": "Choose champion prediction entry",
    "单届演示（跑 1 届完整赛事）": "Single-run demo (simulate 1 full tournament)",
    "Monte Carlo 分析（重复统计夺冠率）": "Monte Carlo analysis (repeat tournaments and estimate champion rates)",
    "快速分析（只统计冠军率，速度最快）": "Fast analysis (champion rates only, fastest)",
    "高阶分析（统计阶段、路线、总决赛转化率和地图表现）": (
        "Advanced analysis (stage funnel, routes, grand-final conversion, and map performance)"
    ),
    "从头开始（完整赛事）": "From the beginning (full tournament)",
    "从指定阶段开始": "From a specific stage",
    "请选择从哪个阶段开始": "Choose the stage to start from",
    "请选择单场模拟阶段": "Choose single-stage simulation stage",
    "当前赛季暂不使用阶段化规则；下面会进行基础单场胜率分析。": (
        "This season does not use stage-based rules yet. The wizard will continue with the basic single-stage win-rate flow."
    ),
    "当前模拟阶段：": "Current simulation stage: ",
    "当前起始阶段：": "Current starting stage: ",
    "后续将模拟：": "Remaining simulation: ",
    "后续将依次模拟：": "Remaining stages to simulate: ",
    "本次会直接使用已保存的上下文继续预测。": "This run will continue directly from the saved context.",
    "下面会只询问继续推演到总决赛所必需的信息。": (
        "Next, the wizard will only ask for the information required to continue to the grand final."
    ),
    "接下来会需要这些信息：": "The wizard will need the following inputs:",
    "请输入序号": "Enter number",
    "输入无效，请重新输入上面的序号。": "Invalid input. Please enter one of the numbers listed above.",
    "未输入任何角色": "No runners were entered.",
    "请选择单场模拟阶段": "Choose single-stage simulation stage",
    "下面会继续询问登场角色、起跑配置、模拟次数和输出格式。": (
        "Next, the wizard will ask for runners, start layout, iteration count, and output format."
    ),
    "请输入 6 名登场角色，使用空格或逗号分隔。": "Enter 6 runners, separated by spaces or commas.",
    "请按上一轮第 1 名到第 6 名的顺序输入 6 名角色，系统会按这个顺序自动生成起跑站位。": (
        "Enter 6 runners in previous-round rank order from 1st to 6th. The wizard will derive the seeded start layout automatically."
    ),
    "请输入角色": "Enter runners",
    "默认起跑配置会根据当前阶段自动适配；如果你想覆盖，下一步可以手动输入自定义起跑。": (
        "The default start layout will be derived automatically for this stage. If you want to override it, you can enter a custom start layout next."
    ),
    "是否覆盖默认起跑配置": "Override the default start layout",
    "请输入自定义起跑配置，例如 1:* 或 -3:10;-2:4,3;-1:8": (
        "Enter a custom start layout, for example 1:* or -3:10;-2:4,3;-1:8"
    ),
    "请输入起跑配置，例如 1:* 或 -3:2;-2:1,4;1:5": (
        "Enter a start layout, for example 1:* or -3:2;-2:1,4;1:5"
    ),
    "请输入 Monte Carlo 模拟次数": "Enter Monte Carlo iteration count",
    "请输入随机种子，留空表示不固定": "Enter random seed, or leave blank for non-fixed randomness",
    "请输入随机种子（留空表示不固定）": "Enter random seed (leave blank for non-fixed randomness)",
    "请输入 workers 数量，0 表示使用 CPU 核心数": "Enter worker count; use 0 for CPU core count",
    "请输入 workers 数量（0 表示 CPU 核心数）": "Enter worker count (0 means CPU core count)",
    "是否输出 JSON 结果": "Output JSON result",
    "已从 ": "Loaded tournament context from ",
    " 载入赛事上下文：": ": ",
    "是/否": "Yes/No",
    "小组赛第一轮": "Group Stage Round 1",
    "小组赛第二轮": "Group Stage Round 2",
    "淘汰赛": "Elimination",
    "败者组": "Losers Bracket",
    "胜者组": "Winners Bracket",
    "总决赛": "Grand Final",
    "小组A第一轮": "Group A Round 1",
    "小组A第二轮": "Group A Round 2",
    "小组B第一轮": "Group B Round 1",
    "小组B第二轮": "Group B Round 2",
    "小组C第一轮": "Group C Round 1",
    "小组C第二轮": "Group C Round 2",
    "淘汰赛A": "Elimination A",
    "淘汰赛B": "Elimination B",
    "败者组第一轮": "Losers Round 1",
    "败者组第二轮": "Losers Round 2",
    "胜者组第二轮": "Winners Round 2",
    "本届参赛角色（18名）": "Season roster (18 runners)",
    "小组赛 A/B/C 分组（3组×6名，可选）": "Group stage A/B/C rosters (3 groups x 6, optional)",
    "小组A第二轮参赛顺序（6名）": "Group A Round 2 entrant order (6)",
    "小组B第一轮参赛角色（6名）": "Group B Round 1 entrants (6)",
    "小组C第一轮参赛角色（6名）": "Group C Round 1 entrants (6)",
    "小组A第二轮晋级角色（前4名）": "Group A Round 2 qualifiers (top 4)",
    "小组B第二轮参赛顺序（6名）": "Group B Round 2 entrant order (6)",
    "小组B第二轮晋级角色（前4名）": "Group B Round 2 qualifiers (top 4)",
    "小组C第二轮参赛顺序（6名）": "Group C Round 2 entrant order (6)",
    "淘汰赛A参赛角色（6名）": "Elimination A entrants (6)",
    "淘汰赛B参赛角色（6名）": "Elimination B entrants (6)",
    "淘汰赛A完整排名（6名）": "Elimination A full ranking (6)",
    "败者组第一轮参赛角色（6名）": "Losers Round 1 entrants (6)",
    "胜者组参赛角色（6名）": "Winners Bracket entrants (6)",
    "败者组第一轮晋级角色（前3名）": "Losers Round 1 qualifiers (top 3)",
    "胜者组直通总决赛角色（前3名）": "Winners direct grand-final qualifiers (top 3)",
    "败者组第二轮参赛角色（6名）": "Losers Round 2 entrants (6)",
    "总决赛参赛角色（6名）": "Grand Final entrants (6)",
    "提供本届赛事全部 18 名参赛角色；若不额外指定分组，系统会随机分配到小组 A/B/C。": (
        "Provide all 18 runners for this tournament. If you do not specify the three groups manually, the wizard will assign them randomly to Groups A/B/C."
    ),
    "如果你已经确定了小组赛分组，可以直接给出 A/B/C 三组各 6 人；否则系统会按 seed 随机分组。": (
        "If the group-stage rosters are already fixed, enter all three groups of 6 directly. Otherwise the wizard will randomize them using the seed."
    ),
    "按小组 A 第一轮的第 1 名到第 6 名顺序输入，系统会据此自动生成第二轮起跑站位。": (
        "Enter Group A Round 1 in finishing order from 1st to 6th. The wizard will derive the Group A Round 2 start layout automatically."
    ),
    "用于继续模拟小组 B 的两轮比赛。": "Used to continue both rounds for Group B.",
    "用于继续模拟小组 C 的两轮比赛。": "Used to continue both rounds for Group C.",
    "小组 A 已经结束，需要补齐这 4 个晋级名额，后续才能拼出淘汰赛阶段的 12 人名单。": (
        "Group A has already finished. These 4 qualifiers are needed to build the 12-runner elimination field."
    ),
    "小组 A 已经结束，需要补齐这 4 个晋级名额。": "Group A has already finished. These 4 qualifiers are required.",
    "小组 B 已经结束，需要补齐这 4 个晋级名额。": "Group B has already finished. These 4 qualifiers are required.",
    "按小组 B 第一轮的第 1 名到第 6 名顺序输入，系统会据此自动生成第二轮起跑站位。": (
        "Enter Group B Round 1 in finishing order from 1st to 6th. The wizard will derive the Group B Round 2 start layout automatically."
    ),
    "按小组 C 第一轮的第 1 名到第 6 名顺序输入，系统会据此自动生成第二轮起跑站位。": (
        "Enter Group C Round 1 in finishing order from 1st to 6th. The wizard will derive the Group C Round 2 start layout automatically."
    ),
    "12 名小组赛晋级者如何分到淘汰赛 A/B 两组，需要在这里确定一半名单。": (
        "This is where you decide half of the 12 qualifiers assigned to Elimination A/B."
    ),
    "补齐淘汰赛另一组名单，后续才能继续拼接胜者组和败者组。": (
        "Fill in the other elimination group so the winners and losers brackets can continue."
    ),
    "用于确定胜者组和败者组各自来自淘汰赛 A 的 3 个席位。": (
        "Used to determine which 3 seats from Elimination A go to the winners bracket and which 3 go to the losers bracket."
    ),
    "用于继续模拟淘汰赛 B。": "Used to continue Elimination B.",
    "这是两场淘汰赛后落入败者组的 6 名角色。": "These are the 6 runners who fell into the losers bracket after the two elimination matches.",
    "这是两场淘汰赛后进入胜者组的 6 名角色。": "These are the 6 runners who advanced to the winners bracket after the two elimination matches.",
    "后续败者组第二轮需要用到这 3 个晋级名额。": "These 3 qualifiers will be needed later in Losers Round 2.",
    "用于继续模拟胜者组并锁定总决赛的前 3 席。": "Used to continue the winners bracket and lock the first 3 seats in the grand final.",
    "这 3 名角色会直接占据总决赛的一半席位，后续需要与败者组第二轮前 3 名合并。": (
        "These 3 runners directly occupy half of the grand-final field and will later be combined with the top 3 from Losers Round 2."
    ),
    "用于继续模拟败者组第二轮，并决出剩余 3 个总决赛席位。": (
        "Used to continue Losers Round 2 and decide the remaining 3 grand-final seats."
    ),
    "从总决赛开始时，冠军预测会退化成单阶段夺冠预测。": (
        "If you start from the grand final, champion prediction becomes a single-stage champion forecast."
    ),
    "小组A第二轮的补录方式": "How to provide Group A Round 2 context",
    "分别输入小组A第二轮顺序，以及小组B/C第一轮名单": (
        "Enter Group A Round 2 order, plus Group B/C Round 1 rosters separately"
    ),
    "输入小组A第一轮完整排名 + 小组B/C第一轮名单（共12名）": (
        "Enter Group A Round 1 full ranking + Group B/C Round 1 rosters (12 total)"
    ),
    "请输入小组A第一轮完整排名（6名）": "Enter the full Group A Round 1 ranking (6)",
    "系统会直接把这 6 名作为小组A第二轮的参赛顺序。": (
        "The wizard will use these 6 runners directly as the Group A Round 2 entrant order."
    ),
    "请输入小组B和小组C第一轮名单（共12名）": "Enter the Group B and Group C Round 1 rosters (12 total)",
    "请按“小组B的 6 名在前，小组C的 6 名在后”的顺序输入，系统会自动拆成两组继续模拟。": (
        "Enter all 12 runners with Group B's 6 first and Group C's 6 second. The wizard will split them automatically."
    ),
    "小组B第一轮的补录方式": "How to provide Group B Round 1 context",
    "分别输入小组A晋级名单，以及小组B/C第一轮名单": (
        "Enter Group A qualifiers plus Group B/C Round 1 rosters separately"
    ),
    "输入小组A第二轮完整排名 + 小组B/C第一轮名单（共12名）": (
        "Enter Group A Round 2 full ranking + Group B/C Round 1 rosters (12 total)"
    ),
    "请输入小组A第二轮完整排名（6名）": "Enter the full Group A Round 2 ranking (6)",
    "系统会自动取前 4 名作为小组A晋级名单。": "The wizard will take the top 4 as Group A qualifiers.",
    "小组B第二轮的补录方式": "How to provide Group B Round 2 context",
    "分别输入小组A晋级名单、小组B第二轮顺序和小组C第一轮名单": (
        "Enter Group A qualifiers, Group B Round 2 order, and the Group C Round 1 roster separately"
    ),
    "输入小组A第二轮完整排名 + 小组B第一轮完整排名 + 小组C第一轮名单": (
        "Enter Group A Round 2 full ranking + Group B Round 1 full ranking + Group C Round 1 roster"
    ),
    "请输入小组B第一轮完整排名（6名）": "Enter the full Group B Round 1 ranking (6)",
    "系统会直接把这 6 名作为小组B第二轮的参赛顺序。": (
        "The wizard will use these 6 runners directly as the Group B Round 2 entrant order."
    ),
    "请输入小组C第一轮参赛角色（6名）": "Enter the Group C Round 1 entrants (6)",
    "这些角色会继续完整跑完小组C的两轮比赛。": "These runners will continue through both Group C rounds.",
    "小组C第一轮的补录方式": "How to provide Group C Round 1 context",
    "分别输入小组A/B晋级名单和小组C第一轮名单": (
        "Enter Group A/B qualifiers and the Group C Round 1 roster separately"
    ),
    "输入小组A/B第二轮完整排名 + 小组C第一轮名单": (
        "Enter Group A/B Round 2 full rankings + the Group C Round 1 roster"
    ),
    "请输入小组B第二轮完整排名（6名）": "Enter the full Group B Round 2 ranking (6)",
    "系统会自动取前 4 名作为小组B晋级名单。": "The wizard will take the top 4 as Group B qualifiers.",
    "小组C第二轮的补录方式": "How to provide Group C Round 2 context",
    "分别输入小组A/B晋级名单和小组C第二轮顺序": (
        "Enter Group A/B qualifiers and the Group C Round 2 order separately"
    ),
    "输入小组A/B第二轮完整排名 + 小组C第一轮完整排名": (
        "Enter Group A/B Round 2 full rankings + the Group C Round 1 full ranking"
    ),
    "请输入小组C第一轮完整排名（6名）": "Enter the full Group C Round 1 ranking (6)",
    "系统会直接把这 6 名作为小组C第二轮的参赛顺序。": (
        "The wizard will use these 6 runners directly as the Group C Round 2 entrant order."
    ),
    "淘汰赛分组的补录方式": "How to provide elimination groups",
    "直接输入淘汰赛 A/B 两组名单": "Enter Elimination A and B rosters directly",
    "输入 12 名晋级者，前 6 名视为淘汰赛 A，后 6 名视为 B": (
        "Enter 12 qualified runners; the first 6 become Elimination A and the last 6 become Elimination B"
    ),
    "请输入 12 名小组赛晋级角色": "Enter the 12 group-stage qualifiers",
    "按“淘汰赛 A 的 6 人在前，淘汰赛 B 的 6 人在后”的顺序输入，系统会自动拆成两组。": (
        "Enter all 12 runners with Elimination A's 6 first and Elimination B's 6 second. The wizard will split them automatically."
    ),
    "淘汰赛B的补录方式": "How to provide Elimination B context",
    "直接输入淘汰赛 A 排名和淘汰赛 B 名单": "Enter the Elimination A ranking and Elimination B roster directly",
    "输入 12 名晋级者和淘汰赛 A 完整排名，自动反推淘汰赛 B 名单": (
        "Enter 12 qualified runners and the Elimination A full ranking to infer the Elimination B roster automatically"
    ),
    "输入本阶段的全部 12 名晋级者；系统会用淘汰赛 A 的完整排名反推淘汰赛 B 的 6 人名单。": (
        "Enter all 12 qualified runners for this stage. The wizard will infer Elimination B from the Elimination A full ranking."
    ),
    "系统会自动把不在这 6 名中的其余晋级者归入淘汰赛 B。": (
        "The wizard will place the remaining qualified runners outside these 6 into Elimination B automatically."
    ),
    "淘汰赛A排名中包含不在这 12 名晋级者里的角色，请重新输入。": (
        "The Elimination A ranking contains runners outside the 12 qualifiers. Please enter it again."
    ),
    "淘汰赛A完整排名需要刚好占用 12 名晋级者中的 6 名，请重新输入。": (
        "The Elimination A full ranking must contain exactly 6 of the 12 qualifiers. Please enter it again."
    ),
    "败者组第一轮的补录方式": "How to provide Losers Round 1 context",
    "直接输入败者组与胜者组当前名单": "Enter the current losers-bracket and winners-bracket rosters directly",
    "输入淘汰赛 A/B 完整排名，自动推导胜者组和败者组名单": (
        "Enter Elimination A/B full rankings to derive the winners and losers bracket rosters automatically"
    ),
    "系统会自动取前 3 名并入胜者组，后 3 名并入败者组。": (
        "The wizard will send the top 3 into the winners bracket and the bottom 3 into the losers bracket automatically."
    ),
    "胜者组的补录方式": "How to provide Winners Bracket context",
    "直接输入胜者组名单和败者组第一轮晋级名单": (
        "Enter the winners-bracket roster and Losers Round 1 qualifiers directly"
    ),
    "输入淘汰赛 A/B 和败者组第一轮完整排名，自动推导剩余上下文": (
        "Enter Elimination A/B and the Losers Round 1 full ranking to derive the remaining context automatically"
    ),
    "系统会自动取前 3 名进入胜者组，后 3 名视作已进入败者组第一轮。": (
        "The wizard will take the top 3 into the winners bracket and treat the bottom 3 as already placed into Losers Round 1."
    ),
    "请输入败者组第一轮完整排名（6名）": "Enter the full Losers Round 1 ranking (6)",
    "系统会自动取前 3 名继续进入败者组第二轮。": (
        "The wizard will take the top 3 to continue into Losers Round 2."
    ),
    "败者组第二轮的补录方式": "How to provide Losers Round 2 context",
    "直接输入败者组第二轮名单和胜者组直通名单": (
        "Enter the Losers Round 2 roster and the direct grand-final qualifiers from the winners bracket"
    ),
    "输入胜者组与败者组第一轮完整排名，自动推导剩余上下文": (
        "Enter the winners-bracket and Losers Round 1 full rankings to derive the remaining context automatically"
    ),
    "请输入胜者组完整排名（6名）": "Enter the full Winners Bracket ranking (6)",
    "系统会自动取前 3 名直通总决赛，后 3 名进入败者组第二轮。": (
        "The wizard will take the top 3 directly into the grand final, and send the bottom 3 into Losers Round 2."
    ),
    "总决赛名单的提供方式": "How to provide the Grand Final roster",
    "直接输入总决赛 6 名角色": "Enter the 6 Grand Final runners directly",
    "输入胜者组与败者组第二轮完整排名，自动生成总决赛名单": (
        "Enter the full winners-bracket and Losers Round 2 rankings to generate the grand-final roster automatically"
    ),
    "系统会自动取前 3 名直通总决赛。": "The wizard will take the top 3 directly into the grand final.",
    "请输入败者组第二轮完整排名（6名）": "Enter the full Losers Round 2 ranking (6)",
    "系统会自动取前 3 名补齐总决赛名单。": "The wizard will take the top 3 to complete the grand-final roster.",
}


@lru_cache(maxsize=None)
def _replacement_pairs(lang: str) -> tuple[tuple[str, str], ...]:
    if lang != "en":
        return ()
    return tuple(sorted(TRANSLATIONS_EN.items(), key=lambda item: len(item[0]), reverse=True))


def translate_interactive_text(text: str, lang: str) -> str:
    if lang != "en":
        return text
    translated = text
    for source, target in _replacement_pairs(lang):
        translated = translated.replace(source, target)
    return translated
