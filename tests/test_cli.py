"""CLI parsing and arg normalization tests.

Split from the original monolithic tests/test_cubie_derby.py to
make selective runs and code review tractable. The shared
imports and helpers (fake RNGs, argparse_namespace fixture, etc.)
live in tests/_shared.py.
"""
from __future__ import annotations

import unittest

from tests._shared import *  # noqa: F401,F403  (test fixtures)


class CliTests(unittest.TestCase):
    def test_parse_custom_start_spec(self):
        self.assertEqual(parse_start_spec("1:10;2:4,3;3:8"), {1: (10,), 2: (4, 3), 3: (8,)})

    def test_parse_custom_start_spec_supports_negative_cells(self):
        self.assertEqual(parse_start_spec("-3:10;-2:4,3;0:8"), {-3: (10,), -2: (4, 3), 0: (8,)})

    def test_normalize_cli_args_preserves_negative_start_value(self):
        self.assertEqual(
            normalize_cli_args(["--start", "-3:10;-2:4,3;0:8", "--runners", "3", "4", "8", "10"]),
            ["--start=-3:10;-2:4,3;0:8", "--runners", "3", "4", "8", "10"],
        )

    def test_parse_random_stack_start_layout(self):
        self.assertEqual(parse_start_layout("0:*"), ({}, 0))

    def test_parse_new_runner_aliases_and_names(self):
        self.assertEqual(parse_runner("sigrika"), 13)
        self.assertEqual(parse_runner("luuk_herssen"), 14)
        self.assertEqual(parse_runner("Luuk Herssen"), 14)
        self.assertEqual(parse_runner("denia"), 15)
        self.assertEqual(parse_runner("hiyuki"), 16)
        self.assertEqual(parse_runner("chisa"), 17)
        self.assertEqual(parse_runner("mornye"), 18)
        self.assertEqual(parse_runner("lynae"), 19)
        self.assertEqual(parse_runner("aemeath"), 20)
        self.assertEqual(parse_runner("augusta"), 21)
        self.assertEqual(parse_runner("luno"), 22)
        self.assertEqual(parse_runner("phrolova"), 23)
        self.assertEqual(parse_runner("西格莉卡"), 13)
        self.assertEqual(parse_runner("陆赫斯"), 14)
        self.assertEqual(parse_runner("达尼娅"), 15)
        self.assertEqual(parse_runner("绯雪"), 16)
        self.assertEqual(parse_runner("千咲"), 17)
        self.assertEqual(parse_runner("莫宁"), 18)
        self.assertEqual(parse_runner("琳奈"), 19)
        self.assertEqual(parse_runner("爱弥斯"), 20)
        self.assertEqual(parse_runner("奥古斯塔"), 21)
        self.assertEqual(parse_runner("尤诺"), 22)
        self.assertEqual(parse_runner("弗洛洛"), 23)

    def test_parse_random_runners_defaults_to_six_unique_ids(self):
        runners = parse_runner_tokens(["random"], rng=random.Random(42))

        self.assertEqual(len(runners), 6)
        self.assertEqual(len(set(runners)), 6)
        self.assertTrue(all(1 <= runner <= 23 for runner in runners))
        self.assertEqual(runners, parse_runner_tokens(["random"], rng=random.Random(42)))

    def test_parse_random_runners_supports_custom_count(self):
        runners = parse_runner_tokens(["random:4"], rng=random.Random(42))

        self.assertEqual(len(runners), 4)
        self.assertEqual(len(set(runners)), 4)

    def test_parse_random_runners_respects_runner_pool(self):
        runner_pool = season_runner_pool(2)
        runners = parse_runner_tokens(["random"], rng=random.Random(42), runner_pool=runner_pool)

        self.assertEqual(len(runners), 6)
        self.assertTrue(set(runners).issubset(set(runner_pool)))

    def test_parse_random_runners_rejects_count_above_runner_pool(self):
        with self.assertRaisesRegex(ValueError, r"1\.\.12"):
            parse_runner_tokens(["random:13"], rng=random.Random(42), runner_pool=season_runner_pool(1))

    def test_parse_random_runners_cannot_mix_explicit_ids(self):
        with self.assertRaisesRegex(ValueError, "cannot be mixed"):
            parse_runner_tokens(["random", "1"], rng=random.Random(42))

    def test_trace_log_writes_one_race_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_path = Path(tmp_dir) / "trace.log"

            exit_code = main(
                [
                    "--season",
                    "2",
                    "--trace-log",
                    str(log_path),
                    "--start",
                    "-3:2;-2:1,4;-1:3,6;0:5",
                    "--runners",
                    "1",
                    "2",
                    "3",
                    "4",
                    "5",
                    "6",
                    "--seed",
                    "42",
                ]
            )

            text = log_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertIn("=== 日志元信息 ===", text)
            self.assertIn("生成时间：", text)
            self.assertIn("赛道长度：32格", text)
            self.assertIn("NPC行动：", text)
            self.assertIn("后退步数：", text)
            self.assertIn("=== 结果 ===", text)
            self.assertIn("长离", text)
            self.assertIn("本轮开始时位置分布：", text)
            self.assertIn("\n--- ", text)
            self.assertIn("行动后位置分布：", text)
            self.assertIn("【判定时机：行动结束】", text)
            self.assertIn("今汐检查行动角色", text)
            self.assertIn("行动结算后是否位于自己紧邻左侧", text)
            self.assertIn("【判定时机：回合结束】", text)
            self.assertIn("长离检查", text)
            self.assertIn("NPC参与排名：否", text)
            self.assertIn("NPC参与排名：是", text)

            round_three_start = text.index("=== 第3轮 ===")
            first_npc_action = text.index("NPC行动：", round_three_start)
            round_three_intro = text[round_three_start:first_npc_action]
            self.assertRegex(round_three_intro, r"第0格（左→右）：\[[^\]]*NPC[^\]]*\]")

            lines = round_three_intro.splitlines()
            order_index = next(i for i, line in enumerate(lines) if line.startswith("本轮行动顺序："))
            order_text = lines[order_index + 1].strip()
            self.assertIn("NPC", order_text)
            self.assertEqual(order_text.count("->") + 1, 7)


if __name__ == "__main__":
    unittest.main()
