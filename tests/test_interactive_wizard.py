"""Interactive wizard / prompts / i18n tests.

Split from the original monolithic tests/test_cubie_derby.py to
make selective runs and code review tractable. The shared
imports and helpers (fake RNGs, argparse_namespace fixture, etc.)
live in tests/_shared.py.
"""
from __future__ import annotations

import unittest

from tests._shared import *  # noqa: F401,F403  (test fixtures)


class InteractiveWizardTests(unittest.TestCase):
    def test_prompt_line_requires_explicit_input_in_chinese(self):
        prompts: list[str] = []

        value = _prompt_line(
            "请输入序号",
            input_fn=lambda prompt: prompts.append(prompt) or "1",
            translate_fn=lambda text: translate_interactive_text(text, "zh"),
        )

        self.assertEqual(value, "1")
        self.assertEqual(prompts, ["请输入序号: "])

    def test_prompt_line_requires_explicit_input_in_english(self):
        prompts: list[str] = []

        value = _prompt_line(
            "请输入序号",
            input_fn=lambda prompt: prompts.append(prompt) or "1",
            translate_fn=lambda text: translate_interactive_text(text, "en"),
        )

        self.assertEqual(value, "1")
        self.assertEqual(prompts, ["Enter number: "])

    def test_prompt_yes_no_requires_explicit_input_in_chinese(self):
        prompts: list[str] = []

        value = _prompt_yes_no(
            "是否输出 JSON 结果",
            input_fn=lambda prompt: prompts.append(prompt) or "是",
            translate_fn=lambda text: translate_interactive_text(text, "zh"),
        )

        self.assertTrue(value)
        self.assertEqual(prompts, ["是否输出 JSON 结果（是/否）: "])

    def test_prompt_yes_no_requires_explicit_input_in_english(self):
        prompts: list[str] = []

        value = _prompt_yes_no(
            "是否输出 JSON 结果",
            input_fn=lambda prompt: prompts.append(prompt) or "no",
            translate_fn=lambda text: translate_interactive_text(text, "en"),
        )

        self.assertFalse(value)
        self.assertEqual(prompts, ["Output JSON result (yes/no): "])

    def test_runner_catalog_lines_follow_prompt_language(self):
        pool = tuple(season_runner_pool(2))

        zh_lines = _runner_catalog_lines(season=2, runner_pool=pool, lang="zh")
        en_lines = _runner_catalog_lines(season=2, runner_pool=pool, lang="en")

        self.assertIn("输入方式：角色编号、中文名或英文别名。", zh_lines)
        self.assertIn("第2季角色目录", zh_lines)
        self.assertTrue(any(line.startswith("  +") for line in zh_lines))
        self.assertTrue(any("1 = 今汐" in line for line in zh_lines))
        self.assertTrue(any("|" in line for line in zh_lines[2:]))
        self.assertFalse(any("/jinhsi" in line for line in zh_lines))
        self.assertIn("Input: runner ID, Chinese name, or English alias.", en_lines)
        self.assertIn("Season 2 runner list", en_lines)
        self.assertTrue(any(line.startswith("  +") for line in en_lines))
        self.assertTrue(any("1 = jinhsi" in line for line in en_lines))
        self.assertTrue(any("|" in line for line in en_lines[2:]))
        self.assertFalse(any("今汐" in line for line in en_lines))

    def test_runner_progress_collapses_earlier_entries_after_threshold(self):
        lines: list[str] = []

        _emit_runner_progress(
            (1, 3, 11, 21, 16),
            expected_count=6,
            prompt_output_fn=lines.append,
            lang="zh",
        )

        self.assertEqual(
            lines,
            [
                "当前已记录 5/6 名（已折叠前 2 名）：",
                "  ... 前 2 名已折叠",
                "   3 = 卡提希娅",
                "   4 = 奥古斯塔",
                "   5 = 绯雪",
                "还需要输入 1 名角色。",
            ],
        )

    def test_interactive_wizard_ui_compacts_previous_steps_into_summary(self):
        lines: list[str] = []
        ui = InteractiveWizardUI(prompt_output_fn=lines.append, lang="zh", compact_mode=True)
        ui.set_summary("season", "赛季 = 第2季")
        ui.set_summary("analysis", "分析 = 单场胜率分析")

        ui.start_block("请选择单场模拟阶段")

        self.assertEqual(lines[0], "\x1b[2J\x1b[H")
        self.assertIn("当前摘要", lines)
        self.assertIn("  赛季 = 第2季", lines)
        self.assertIn("  分析 = 单场胜率分析", lines)
        self.assertEqual(lines[-3:], ["=" * 24, "请选择单场模拟阶段", "=" * 24])

    def test_interactive_wizard_ui_can_refresh_summary_without_new_block(self):
        lines: list[str] = []
        ui = InteractiveWizardUI(prompt_output_fn=lines.append, lang="zh", compact_mode=True)
        ui.set_summary("season", "赛季 = 第2季")
        ui.start_block("并行设置")

        lines.clear()
        ui.set_summary("workers", "并行 = 0")
        ui.refresh_summary()

        self.assertEqual(lines[0], "\x1b[2J\x1b[H")
        self.assertIn("当前摘要", lines)
        self.assertIn("  赛季 = 第2季", lines)
        self.assertIn("  并行 = 0", lines)
        self.assertNotIn("并行设置", lines)

    def test_core_skill_trace_logger_uses_buffer_instead_of_stdout(self):
        state = RaceSkillState()
        trace = TraceLogger()
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            self.assertEqual(check_hiyuki_bonus(state, trace), 0)

        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("绯雪技能未生效：", trace.text())

    def test_main_interactive_champion_prediction_prompts_for_mode(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "1",
                "2",
                "12",
                "1",
                "11 12 13 14 15 16",
                "n",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--seed",
                    "7",
                ]
            )

        text = stdout.getvalue()
        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("请选择分析大类", prompt_text)
        self.assertIn("你正在进入“赛事冠军预测”", prompt_text)
        self.assertIn("请选择冠军预测方式", prompt_text)
        self.assertIn("请选择冠军预测入口", prompt_text)
        self.assertNotIn("起始阶段：总决赛", text)
        self.assertNotIn("剩余赛程：", text)
        self.assertIn("总决赛", text)

    def test_main_interactive_champion_prediction_can_start_from_beginning(self):
        stdout = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "1",
                "1",
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "group-a-round-1")
        self.assertEqual(data["stages"][0]["match_type"], "group-round-1")
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")

    def test_main_interactive_champion_prediction_monte_carlo_json(self):
        stdout = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "2",
                "12",
                "1",
                "11 12 13 14 15 16",
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "monte-carlo",
                    "--iterations",
                    "4",
                    "--workers",
                    "1",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["season"], 2)
        self.assertEqual(data["iterations"], 4)
        self.assertEqual(data["start_entry_point"], "grand-final")
        self.assertEqual({row["runner"] for row in data["rows"]}, {11, 12, 13, 14, 15, 16})

    def test_main_interactive_champion_monte_carlo_from_start_skips_stage_customization_prompts(self):
        class TtyStringIO(io.StringIO):
            def isatty(self) -> bool:
                return True

        stdout = io.StringIO()
        stderr = TtyStringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "1",
                "1",
                "n",
                "4",
                "1",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "monte-carlo",
                ]
            )

        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("请选择参赛角色设置", prompt_text)
        self.assertIn("本届参赛角色（18名）", prompt_text)
        self.assertNotIn("随机种子", prompt_text)
        self.assertNotIn("请选择小组赛分组方式", prompt_text)
        self.assertNotIn("上下文 =", prompt_text)

    def test_main_interactive_champion_monte_carlo_from_start_accepts_custom_roster(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "1",
                "2",
                "1 2 3 4 6 11 12 13 14 15 16 17 18 19 20 21 22 23",
                "4",
                "1",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "monte-carlo",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "group-a-round-1")
        self.assertEqual({row["runner"] for row in data["rows"]}, {1, 2, 3, 4, 6, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23})
        self.assertIn("本届参赛角色（18名）", prompt_text)
        self.assertNotIn("请选择小组赛分组方式", prompt_text)

    def test_main_interactive_single_stage_elimination_monte_carlo_json(self):
        stdout = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "3",
                "1",
                "11 12 13 14 15 16",
                "n",
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--iterations",
                    "4",
                    "--workers",
                    "1",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["iterations"], 4)
        self.assertEqual(data["config"]["match_type"], "elimination")
        self.assertEqual(data["config"]["map_label"], "淘汰赛阶段地图")
        self.assertEqual(data["config"]["qualify_cutoff"], 3)
        self.assertEqual(data["config"]["runners"], [11, 12, 13, 14, 15, 16])

    def test_main_without_args_enters_interactive_wizard(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "2",
                "1",
                "1",
                "2",
                "12",
                "1",
                "11 12 13 14 15 16",
                "7",
                "n",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main([])

        text = stdout.getvalue()
        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Choose language / 请选择语言", prompt_text)
        self.assertIn("请选择赛季", prompt_text)
        self.assertIn("请选择分析大类", prompt_text)
        self.assertNotIn("起始阶段：总决赛", text)
        self.assertNotIn("剩余赛程：", text)

    def test_main_without_args_can_choose_season_one_simulation(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "1",
                "1",
                "1 2 3 4 5 6",
                "1:*",
                "7",
                "y",
                "4",
                "1",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main([])

        data = json.loads(stdout.getvalue())
        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("请选择赛季", prompt_text)
        self.assertIn("当前第1季交互向导先提供单场胜率分析", prompt_text)
        self.assertEqual(data["config"]["season"], 1)
        self.assertNotIn("match_type", data["config"])
        self.assertEqual(data["config"]["runners"], [1, 2, 3, 4, 5, 6])

    def test_main_with_prefill_args_still_enters_interactive_wizard(self):
        stdout = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "2",
                "3",
                "1",
                "11 12 13 14 15 16",
                "n",
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--season",
                    "2",
                    "--iterations",
                    "4",
                    "--workers",
                    "1",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["iterations"], 4)
        self.assertEqual(data["config"]["match_type"], "elimination")
        self.assertEqual(data["config"]["runners"], [11, 12, 13, 14, 15, 16])

    def test_main_without_args_can_choose_english_first(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "2",
                "1",
                "1",
                "2",
                "12",
                "1",
                "11 12 13 14 15 16",
                "7",
                "n",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main([])

        prompt_text = stderr.getvalue()
        text = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Choose language / 请选择语言", prompt_text)
        self.assertIn("Choose season", prompt_text)
        self.assertIn("Choose analysis branch", prompt_text)
        self.assertIn("Grand Final", text)

    def test_main_from_start_champion_prediction_uses_full_season_roster_automatically(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "2",
                "1",
                "1",
                "1",
                "1",
                "1",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(["--seed", "7", "--json"])

        prompt_text = stderr.getvalue()
        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn("请选择参赛角色设置", prompt_text)
        self.assertIn("请选择小组赛分组方式", prompt_text)
        self.assertNotIn("请输入 18 名角色", prompt_text)
        self.assertNotIn("本赛季可用角色", prompt_text)
        self.assertNotIn("后续将依次模拟：", prompt_text)
        self.assertNotIn("是否手动输入", prompt_text)
        self.assertEqual(data["start_entry_point"], "group-a-round-1")

    def test_main_interactive_can_save_tournament_context_json(self):
        stdout = io.StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            context_path = Path(temp_dir) / "grand-final-context.json"
            with patch(
                "builtins.input",
                side_effect=[
                    "2",
                    "12",
                    "1",
                    "11 12 13 14 15 16",
                ],
            ), contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--interactive",
                        "--season",
                        "2",
                        "--champion-prediction",
                        "random",
                        "--seed",
                        "7",
                        "--json",
                        "--tournament-context-out",
                        str(context_path),
                    ]
                )

            data = json.loads(stdout.getvalue())
            saved = json.loads(context_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(data["season"], 2)
        self.assertEqual(saved["entry_point"], "grand-final")
        self.assertEqual(saved["inputs"]["grand-final-entrants"], [11, 12, 13, 14, 15, 16])

    def test_main_interactive_can_load_tournament_context_json(self):
        stdout = io.StringIO()
        request = build_tournament_entry_request(
            season=2,
            entry_point="grand-final",
            inputs={"grand-final-entrants": (11, 12, 13, 14, 15, 16)},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            context_path = Path(temp_dir) / "grand-final-context.json"
            context_path.write_text(
                json.dumps(tournament_entry_request_to_dict(request), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with patch(
                "builtins.input",
                side_effect=AssertionError("interactive context load should not prompt for input"),
            ), contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--interactive",
                        "--champion-prediction",
                        "random",
                        "--seed",
                        "7",
                        "--json",
                        "--tournament-context-in",
                        str(context_path),
                    ]
                )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["season"], 2)
        self.assertEqual(data["start_entry_point"], "grand-final")
        self.assertEqual({stage["match_type"] for stage in data["stages"]}, {"grand-final"})

    def test_main_interactive_grand_final_can_derive_finalists_from_rankings(self):
        stdout = io.StringIO()
        pool = tuple(season_runner_pool(2))
        winners = pool[:6]
        losers = pool[6:12]

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "12",
                "2",
                " ".join(str(runner) for runner in winners),
                " ".join(str(runner) for runner in losers),
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        finalists = list(winners[:3] + losers[:3])
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "grand-final")
        self.assertEqual(data["stages"][0]["entrants"], finalists)
        self.assertIn(data["champion"], finalists)

    def test_main_interactive_winners_round_can_derive_qualifiers_from_full_ranking(self):
        stdout = io.StringIO()
        pool = tuple(season_runner_pool(2))
        elimination_a = pool[:6]
        elimination_b = pool[6:12]
        losers_round_one = pool[12:18]

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "10",
                "2",
                " ".join(str(runner) for runner in elimination_a),
                " ".join(str(runner) for runner in elimination_b),
                " ".join(str(runner) for runner in losers_round_one),
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "winners-round-2")
        self.assertEqual(data["stages"][0]["match_type"], "winners-bracket")
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")

    def test_main_interactive_elimination_a_can_split_ordered_qualifiers(self):
        stdout = io.StringIO()
        pool = tuple(season_runner_pool(2))
        qualifiers = pool[:12]

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "7",
                "2",
                " ".join(str(runner) for runner in qualifiers),
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "elimination-a")
        self.assertEqual(data["stages"][0]["entrants"], list(qualifiers[:6]))
        self.assertEqual(data["stages"][1]["entrants"], list(qualifiers[6:12]))
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")

    def test_main_interactive_elimination_b_can_derive_remaining_group(self):
        stdout = io.StringIO()
        pool = tuple(season_runner_pool(2))
        qualifiers = pool[:12]
        elimination_a = qualifiers[:6]

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "8",
                "2",
                " ".join(str(runner) for runner in qualifiers),
                " ".join(str(runner) for runner in elimination_a),
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "elimination-b")
        self.assertEqual(data["stages"][0]["entrants"], list(qualifiers[6:12]))
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")

    def test_main_interactive_group_a_round_two_can_split_remaining_groups(self):
        stdout = io.StringIO()
        pool = tuple(season_runner_pool(2))
        group_a = pool[:6]
        remaining = pool[6:18]

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "2",
                "2",
                " ".join(str(runner) for runner in group_a),
                " ".join(str(runner) for runner in remaining),
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "group-a-round-2")
        self.assertEqual(data["stages"][0]["entrants"], list(group_a))
        self.assertEqual(data["stages"][1]["entrants"], list(remaining[:6]))
        self.assertEqual(data["stages"][3]["entrants"], list(remaining[6:12]))
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")

    def test_main_interactive_group_c_round_two_can_derive_from_rankings(self):
        stdout = io.StringIO()
        pool = tuple(season_runner_pool(2))
        group_a = pool[:6]
        group_b = pool[6:12]
        group_c = pool[12:18]

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "6",
                "2",
                " ".join(str(runner) for runner in group_a),
                " ".join(str(runner) for runner in group_b),
                " ".join(str(runner) for runner in group_c),
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "group-c-round-2")
        self.assertEqual(data["stages"][0]["entrants"], list(group_c))
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")

    def test_main_interactive_winners_round_can_derive_from_elimination_and_losers_rankings(self):
        stdout = io.StringIO()
        pool = tuple(season_runner_pool(2))
        elimination_a = pool[:6]
        elimination_b = pool[6:12]
        losers_round_one = pool[12:18]

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "10",
                "2",
                " ".join(str(runner) for runner in elimination_a),
                " ".join(str(runner) for runner in elimination_b),
                " ".join(str(runner) for runner in losers_round_one),
            ],
        ), contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["start_entry_point"], "winners-round-2")
        self.assertEqual(data["stages"][0]["entrants"], list(elimination_a[:3] + elimination_b[:3]))
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")

    def test_main_interactive_champion_prediction_prompts_stage_guidance(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "12",
                "1",
                "11 12 13 14 15 16",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("下一步", prompt_text)
        self.assertIn("进度会保留在顶部摘要中", prompt_text)
        self.assertIn("接下来会需要这些信息：", prompt_text)
        self.assertIn("总决赛参赛角色（6名）", prompt_text)

    def test_main_interactive_simulation_prompts_are_readable(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "3",
                "1",
                "11 12 13 14 15 16",
                "n",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--iterations",
                    "4",
                    "--workers",
                    "1",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("请选择分析大类", prompt_text)
        self.assertIn("你正在进入“单场胜率分析”", prompt_text)
        self.assertIn("请选择单场模拟阶段", prompt_text)
        self.assertIn("当前模拟阶段：淘汰赛", prompt_text)
        self.assertIn("输入说明", prompt_text)
        self.assertIn("输入方式：角色编号、中文名或英文别名", prompt_text)
        self.assertIn("角色目录", prompt_text)
        self.assertIn("开始输入", prompt_text)
        self.assertIn("1 = 今汐", prompt_text)
        self.assertIn("|", prompt_text)
        self.assertIn("请输入 6 名登场角色", prompt_text)
        self.assertIn("默认起跑配置会根据当前阶段自动适配", prompt_text)
        self.assertIn("请选择单场分析方式", prompt_text)

    def test_main_interactive_simulation_accepts_incremental_runner_entry(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "3",
                "1",
                "1",
                "3",
                "11",
                "21",
                "16",
                "22",
                "n",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--iterations",
                    "4",
                    "--workers",
                    "1",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["config"]["runners"], [1, 3, 11, 21, 16, 22])
        self.assertIn("当前已记录 5/6 名（已折叠前 2 名）：", prompt_text)
        self.assertIn("... 前 2 名已折叠", prompt_text)
        self.assertIn("3 = 卡提希娅", prompt_text)
        self.assertIn("5 = 绯雪", prompt_text)
        self.assertIn("还需要输入 1 名角色。", prompt_text)

    def test_main_interactive_simulation_prompts_support_english(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "3",
                "1",
                "11 12 13 14 15 16",
                "n",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--interactive-language",
                    "en",
                    "--season",
                    "2",
                    "--iterations",
                    "4",
                    "--workers",
                    "1",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Choose analysis branch", prompt_text)
        self.assertIn("Choose single-stage simulation stage", prompt_text)
        self.assertIn("Current simulation stage: Elimination", prompt_text)
        self.assertIn("Input", prompt_text)
        self.assertIn("Input: runner ID, Chinese name, or English alias.", prompt_text)
        self.assertIn("Runner Catalog", prompt_text)
        self.assertIn("Enter Runners", prompt_text)
        self.assertIn("1 = jinhsi", prompt_text)
        self.assertIn("|", prompt_text)
        self.assertIn("Enter 6 runners", prompt_text)
        self.assertIn("Choose single-stage analysis mode", prompt_text)

    def test_main_interactive_simulation_can_write_trace_log_file(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as temp_dir:
            trace_path = Path(temp_dir) / "trace.log"
            with patch(
                "builtins.input",
                side_effect=[
                    "2",
                    "3",
                    "2",
                    "11 12 13 14 15 16",
                    "n",
                    "y",
                ],
            ), patch(
                "cubie_derby_core.champion_interactive.default_trace_log_path",
                return_value=trace_path,
            ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = main(
                    [
                        "--interactive",
                        "--season",
                        "2",
                        "--iterations",
                        "4",
                        "--workers",
                        "1",
                        "--seed",
                        "7",
                        "--json",
                    ]
                )

            data = json.loads(stdout.getvalue())
            trace_text = trace_path.read_text(encoding="utf-8")
            prompt_text = stderr.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertEqual(data["iterations"], 1)
            self.assertTrue(trace_path.exists())
            self.assertIn("=== 日志元信息 ===", trace_text)
            self.assertIn("赛道类型：淘汰赛阶段地图", trace_text)
            self.assertIn("=== 结果 ===", trace_text)
            self.assertIn('"ranking"', trace_text)
            self.assertIn("过程日志已写入", prompt_text)

    def test_main_interactive_champion_prediction_accepts_incremental_runner_entry(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "2",
                "12",
                "1",
                "11",
                "12",
                "13",
                "14",
                "15",
                "16",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        data = json.loads(stdout.getvalue())
        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["stages"][0]["entrants"], [11, 12, 13, 14, 15, 16])
        self.assertIn("当前已记录 5/6 名（已折叠前 2 名）：", prompt_text)
        self.assertIn("... 前 2 名已折叠", prompt_text)
        self.assertIn("3 = 西格莉卡", prompt_text)
        self.assertIn("5 = 达尼娅", prompt_text)
        self.assertIn("还需要输入 1 名角色。", prompt_text)

    def test_main_interactive_champion_prompts_support_english(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "1",
                "2",
                "12",
                "1",
                "11 12 13 14 15 16",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--interactive-language",
                    "en",
                    "--season",
                    "2",
                    "--seed",
                    "7",
                    "--json",
                ]
            )

        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Choose analysis branch", prompt_text)
        self.assertIn("Choose champion prediction mode", prompt_text)
        self.assertIn("Choose champion prediction entry", prompt_text)
        self.assertIn("progress stays visible in the summary above", prompt_text)
        self.assertIn("How to provide the Grand Final roster", prompt_text)

    def test_main_interactive_champion_monte_carlo_refreshes_summary_before_progress(self):
        class TtyStringIO(io.StringIO):
            def isatty(self) -> bool:
                return True

        stdout = io.StringIO()
        stderr = TtyStringIO()

        with patch(
            "builtins.input",
            side_effect=[
                "1",
                "1",
                "1",
                "n",
                "4",
                "0",
            ],
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--interactive",
                    "--season",
                    "2",
                    "--champion-prediction",
                    "monte-carlo",
                    "--seed",
                    "7",
                ]
            )

        prompt_text = stderr.getvalue()
        self.assertEqual(exit_code, 0)
        workers_match = re.search(r"并行\s+= 0", prompt_text)
        self.assertIsNotNone(workers_match)
        self.assertIn("冠军预测进度", prompt_text)
        self.assertLess(workers_match.start(), prompt_text.find("冠军预测进度"))


if __name__ == "__main__":
    unittest.main()
