from __future__ import annotations


NPC_ID = -1
JINHSI_ID = 1
CHANGLI_ID = 2
CALCHARO_ID = 3
SHOREKEEPER_ID = 4
CAMELLYA_ID = 5
POTATO_ID = 6
ROCCIA_ID = 7
BRANT_ID = 8
CANTARELLA_ID = 9
ZANI_ID = 10
CARTETHYIA_ID = 11
PHOEBE_ID = 12
SIGRIKA_ID = 13
LUUK_HERSSEN_ID = 14
DENIA_ID = 15
HIYUKI_ID = 16
CHISA_ID = 17
MORNYE_ID = 18
LYNAE_ID = 19
AEMEATH_ID = 20
AUGUSTA_ID = 21
LUNO_ID = 22
PHROLOVA_ID = 23

SEASON1_RUNNER_POOL = (
    JINHSI_ID,
    CHANGLI_ID,
    CALCHARO_ID,
    SHOREKEEPER_ID,
    CAMELLYA_ID,
    POTATO_ID,
    ROCCIA_ID,
    BRANT_ID,
    CANTARELLA_ID,
    ZANI_ID,
    CARTETHYIA_ID,
    PHOEBE_ID,
)
SEASON2_RUNNER_POOL = (
    JINHSI_ID,
    CHANGLI_ID,
    CALCHARO_ID,
    SHOREKEEPER_ID,
    POTATO_ID,
    CARTETHYIA_ID,
    PHOEBE_ID,
    SIGRIKA_ID,
    LUUK_HERSSEN_ID,
    DENIA_ID,
    HIYUKI_ID,
    CHISA_ID,
    MORNYE_ID,
    LYNAE_ID,
    AEMEATH_ID,
    AUGUSTA_ID,
    LUNO_ID,
    PHROLOVA_ID,
)

SKILL_RUNNERS = frozenset(
    {
        JINHSI_ID,
        CHANGLI_ID,
        CALCHARO_ID,
        SHOREKEEPER_ID,
        CAMELLYA_ID,
        POTATO_ID,
        ROCCIA_ID,
        BRANT_ID,
        CANTARELLA_ID,
        ZANI_ID,
        CARTETHYIA_ID,
        PHOEBE_ID,
        SIGRIKA_ID,
        LUUK_HERSSEN_ID,
        DENIA_ID,
        HIYUKI_ID,
        CHISA_ID,
        MORNYE_ID,
        LYNAE_ID,
        AEMEATH_ID,
        AUGUSTA_ID,
        LUNO_ID,
        PHROLOVA_ID,
    }
)
RANDOM_RUNNER_ALIASES = frozenset({"random", "rand", "随机"})

RUNNER_NAMES: dict[int, str] = {
    JINHSI_ID: "今汐",
    CHANGLI_ID: "长离",
    CALCHARO_ID: "卡卡罗",
    SHOREKEEPER_ID: "守岸人",
    CAMELLYA_ID: "椿",
    POTATO_ID: "小土豆",
    ROCCIA_ID: "洛可可",
    BRANT_ID: "布兰特",
    CANTARELLA_ID: "坎特蕾拉",
    ZANI_ID: "赞妮",
    CARTETHYIA_ID: "卡提希娅",
    PHOEBE_ID: "菲比",
    SIGRIKA_ID: "西格莉卡",
    LUUK_HERSSEN_ID: "陆赫斯",
    DENIA_ID: "达尼娅",
    HIYUKI_ID: "绯雪",
    CHISA_ID: "千咲",
    MORNYE_ID: "莫宁",
    LYNAE_ID: "琳奈",
    AEMEATH_ID: "爱弥斯",
    AUGUSTA_ID: "奥古斯塔",
    LUNO_ID: "尤诺",
    PHROLOVA_ID: "弗洛洛",
}

RUNNER_ALIASES: dict[str, int] = {
    "jinhsi": JINHSI_ID,
    "changli": CHANGLI_ID,
    "calcharo": CALCHARO_ID,
    "shorekeeper": SHOREKEEPER_ID,
    "camellya": CAMELLYA_ID,
    "potato": POTATO_ID,
    "roccia": ROCCIA_ID,
    "brant": BRANT_ID,
    "cantarella": CANTARELLA_ID,
    "zani": ZANI_ID,
    "cartethyia": CARTETHYIA_ID,
    "phoebe": PHOEBE_ID,
    "sigrika": SIGRIKA_ID,
    "luuk": LUUK_HERSSEN_ID,
    "luuk herssen": LUUK_HERSSEN_ID,
    "luuk-herssen": LUUK_HERSSEN_ID,
    "luuk_herssen": LUUK_HERSSEN_ID,
    "luukherssen": LUUK_HERSSEN_ID,
    "denia": DENIA_ID,
    "hiyuki": HIYUKI_ID,
    "chisa": CHISA_ID,
    "mornye": MORNYE_ID,
    "lynae": LYNAE_ID,
    "aemeath": AEMEATH_ID,
    "augusta": AUGUSTA_ID,
    "luno": LUNO_ID,
    "phrolova": PHROLOVA_ID,
}

NAME_TO_RUNNER: dict[str, int] = {name: runner for runner, name in RUNNER_NAMES.items()}
