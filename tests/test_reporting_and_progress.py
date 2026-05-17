"""Reporting (formatters, JSON, progress bar) tests.

Split from the original monolithic tests/test_cubie_derby.py to
make selective runs and code review tractable. The shared
imports and helpers (fake RNGs, argparse_namespace fixture, etc.)
live in tests/_shared.py.
"""
from __future__ import annotations

import unittest

from tests._shared import *  # noqa: F401,F403  (test fixtures)


class ReportingAndProgressTests(unittest.TestCase):
    def test_format_summary_uses_chinese_aligned_table(self):
        config = RaceConfig(
            runners=(13, 14, 15, 16),
            track_length=8,
            start_grid=make_start_grid(8, {0: (13, 14, 15, 16)}),
            name="自定义",
        )
        summary = run_monte_carlo(config, 12, seed=3)

        text = format_summary(summary)

        self.assertIn("赛制：自定义", text)
        self.assertIn("角色", text)
        self.assertIn("晋级率", text)
        self.assertIn("晋级统计：前4名", text)
        self.assertIn("用时：未统计", text)
        self.assertIn("速度：未统计", text)
        self.assertIn("推荐选择：", text)
        self.assertNotIn("夺冠次数", text)
        self.assertNotIn("Scenario:", text)
        self.assertNotIn("win_rate", text)

        lines = text.splitlines()
        header_index = next(i for i, line in enumerate(lines) if line.startswith("角色"))
        table_lines = lines[header_index : header_index + 2 + len(config.runners)]
        expected_width = display_width(table_lines[0])
        self.assertTrue(all(display_width(line) == expected_width for line in table_lines))

    def test_format_summary_shows_elapsed_time_when_recorded(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
        )
        summary = with_elapsed(run_monte_carlo(config, 10, seed=1), 0.5)

        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertIn("用时：500 ms", text)
        self.assertIn("速度：20 局/秒", text)
        self.assertEqual(data["elapsed_seconds"], 0.5)
        self.assertEqual(data["races_per_second"], 20.0)

    def test_format_summary_uses_custom_config_name(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
            name="自定义",
        )
        summary = run_monte_carlo(config, 10, seed=1)

        text = format_summary(summary)

        self.assertIn("赛制：自定义", text)

    def test_format_summary_includes_custom_start_layout(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
            name="自定义",
        )
        summary = run_monte_carlo(config, 10, seed=1)

        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertIn("登场角色：卡卡罗, 守岸人, 布兰特, 赞妮", text)
        self.assertIn("自定义站位：第1格：[赞妮]；第2格：[守岸人, 卡卡罗]；第3格：[布兰特]", text)
        self.assertEqual(data["config"]["start_layout"], "第1格：[赞妮]；第2格：[守岸人, 卡卡罗]；第3格：[布兰特]")
        self.assertEqual(data["config"]["start_grid"], {"1": [10], "2": [4, 3], "3": [8]})

    def test_format_summary_includes_map_label_when_available(self):
        config = RaceConfig(
            runners=(11, 12, 13, 14, 15, 16),
            track_length=32,
            start_grid={},
            season=2,
            map_label="淘汰赛阶段地图",
            random_start_stack=True,
            random_start_position=1,
            name="淘汰赛",
        )
        summary = run_monte_carlo(config, 10, seed=1)

        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertIn("赛道类型：淘汰赛阶段地图", text)
        self.assertEqual(data["config"]["map_label"], "淘汰赛阶段地图")

    def test_format_summary_includes_random_stack_start_and_entrants(self):
        config = RaceConfig(
            runners=(11, 12, 13, 14, 15, 16),
            track_length=32,
            start_grid={},
            season=2,
            random_start_stack=True,
            random_start_position=1,
            name="自定义",
        )

        summary = run_monte_carlo(config, 10, seed=1)
        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertIn("登场角色：卡提希娅, 菲比, 西格莉卡, 陆赫斯, 达尼娅, 绯雪", text)
        self.assertIn("起跑配置：第1格（全部登场角色同格，每局随机堆叠顺序）", text)
        self.assertEqual(
            data["config"]["start_layout"],
            "第1格（全部登场角色同格，每局随机堆叠顺序）",
        )

    def test_format_simulation_overview_lines_supports_pending_status(self):
        config = RaceConfig(
            runners=(3, 4, 8, 10),
            track_length=24,
            start_grid=make_start_grid(24, {1: (10,), 2: (4, 3), 3: (8,)}),
            season=2,
            name="自定义",
        )

        lines = format_simulation_overview_lines(config, 1_000_000, pending=True)

        self.assertEqual(
            lines,
            [
                "赛制：自定义",
                "赛季：第2季",
                "登场角色：卡卡罗, 守岸人, 布兰特, 赞妮",
                "模拟次数：1,000,000",
                "赛道长度：24格",
                "晋级统计：前4名",
                "自定义站位：第1格：[赞妮]；第2格：[守岸人, 卡卡罗]；第3格：[布兰特]",
            ],
        )

    def test_grand_final_summary_hides_qualify_stats(self):
        config = RaceConfig(
            runners=(11, 12, 13, 14, 15, 16),
            track_length=32,
            start_grid={1: (11, 12, 13, 14, 15, 16)},
            qualify_cutoff=1,
            season=2,
            match_type="grand-final",
            show_qualify_stats=False,
            name="总决赛",
        )

        summary = run_monte_carlo(config, 10, seed=1)
        text = format_summary(summary)
        data = summary_to_dict(summary)

        self.assertNotIn("晋级率", text)
        self.assertNotIn("晋级统计", text)
        self.assertFalse(data["config"]["show_qualify_stats"])
        self.assertNotIn("qualify_cutoff", data["config"])
        self.assertNotIn("qualify_rate", data["rows"][0])

    def test_progress_bar_renders_zero_percent_immediately(self):
        stream = io.StringIO()

        progress = ProgressBar(100, "模拟进度", stream=stream)

        output = stream.getvalue()
        self.assertIn("模拟进度", output)
        self.assertIn("0/100", output)
        self.assertIn("0.00%", output)
        progress.close()

    def test_parallel_task_count_uses_more_tasks_than_workers(self):
        self.assertEqual(parallel_task_count(1_000_000, 8), 64)
        self.assertEqual(parallel_task_count(10, 8), 10)
        self.assertEqual(parallel_task_count(100, 1), 8)

    def test_champion_parallel_task_count_uses_finer_chunks_for_progress(self):
        self.assertEqual(champion_parallel_task_count(1_000_000, 8), 128)
        self.assertEqual(champion_parallel_task_count(10, 8), 10)
        self.assertEqual(champion_parallel_task_count(100, 1), 8)

    def test_champion_progress_batch_size_reports_more_frequently(self):
        self.assertEqual(champion_progress_batch_size(500), 1)
        self.assertEqual(champion_progress_batch_size(1_000_000), 1_000)
        self.assertLess(champion_progress_batch_size(1_000_000), progress_batch_size(1_000_000))

    def test_split_iterations_evenly_distributes_chunk_sizes(self):
        chunk_sizes = split_iterations(100, 12)

        self.assertEqual(len(chunk_sizes), 12)
        self.assertEqual(sum(chunk_sizes), 100)
        self.assertLessEqual(max(chunk_sizes) - min(chunk_sizes), 1)
        self.assertTrue(all(size > 0 for size in chunk_sizes))


if __name__ == "__main__":
    unittest.main()
