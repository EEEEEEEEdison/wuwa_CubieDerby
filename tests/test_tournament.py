"""Tournament plans, entry points, simulation, prediction tests.

Split from the original monolithic tests/test_cubie_derby.py to
make selective runs and code review tractable. The shared
imports and helpers (fake RNGs, argparse_namespace fixture, etc.)
live in tests/_shared.py.
"""
from __future__ import annotations

import unittest

from tests._shared import *  # noqa: F401,F403  (test fixtures)


class TournamentTests(unittest.TestCase):
    def test_season_runner_pool_matches_expected_rosters(self):
        self.assertEqual(season_runner_pool(1), tuple(range(1, 13)))
        self.assertEqual(season_runner_pool(2), (1, 2, 3, 4, 6, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23))

    def test_season_roster_combination_count_matches_expected_value(self):
        self.assertEqual(season_roster_combination_count(2, 6), 18564)

    def test_season_roster_scan_aggregates_all_combinations(self):
        args = argparse_namespace(
            season=1,
            start="1:*",
            field_size=2,
            iterations=3,
            workers=1,
        )

        summary = run_season_roster_scan(args)
        text = format_season_roster_scan_summary(summary)
        data = season_roster_scan_to_dict(summary)

        self.assertEqual(summary.combination_count, 66)
        self.assertEqual(summary.total_simulated_races, 198)
        self.assertEqual({row.runner for row in summary.rows}, set(range(1, 13)))
        self.assertTrue(all(row.combination_count == 11 for row in summary.rows))
        self.assertEqual(sum(row.wins for row in summary.rows), summary.total_simulated_races)
        self.assertIn("赛季角色池遍历统计：", text)
        self.assertIn("参赛组合", text)
        self.assertIn("综合推荐：", text)
        self.assertEqual(data["combination_count"], 66)
        self.assertEqual(data["total_simulated_races"], 198)
        self.assertEqual(len(data["rows"]), 12)

    def test_season_roster_scan_requires_reusable_star_start(self):
        args = argparse_namespace(
            season=2,
            start="-3:11;-2:16,14;-1:12,13;1:15",
            field_size=6,
        )

        with self.assertRaisesRegex(ValueError, "requires a reusable '\\*' start"):
            run_season_roster_scan(args)

    def test_simulate_stage_group_round_one_emits_round_two_layout(self):
        stage = simulate_stage(
            season=2,
            match_type="group-round-1",
            runners=(11, 12, 13, 14, 15, 16),
            rng=random.Random(1),
        )

        self.assertEqual(stage.match_type, "group-round-1")
        self.assertEqual(len(stage.ranking), 6)
        self.assertEqual(stage.qualified_runners, stage.ranking)
        self.assertIsNotNone(stage.next_stage_start_spec)
        self.assertIn("0:", stage.next_stage_start_spec)
        self.assertIn("-1:", stage.next_stage_start_spec)

    def test_simulate_tournament_returns_complete_season_two_flow(self):
        result = simulate_tournament(2, random.Random(1))
        text = format_tournament_result(result)

        self.assertEqual(result.season, 2)
        self.assertEqual(len(result.stages), 12)
        self.assertEqual(result.stages[0].title, "小组赛第一轮 A组")
        self.assertEqual(result.stages[-1].title, "总决赛")
        self.assertIn(result.champion, season_runner_pool(2))
        self.assertIn("总决赛", text)
        self.assertIn("冠军", text)
        self.assertIn("起跑规则：随机", text)
        self.assertIn("下一轮起跑规则：排名顺序（1.", text)
        self.assertIn("排名：1.", text)
        self.assertNotIn(" -> ", text)

    def test_tournament_phase_choices_cover_explicit_season_two_flow(self):
        self.assertEqual(
            tournament_phase_choices(2),
            (
                "group-round-1",
                "group-round-2",
                "elimination",
                "losers-round-1",
                "winners-round-2",
                "losers-round-2",
                "grand-final",
            ),
        )

    def test_tournament_entry_point_choices_cover_stage_by_stage_flow(self):
        self.assertEqual(
            tournament_entry_point_choices(2),
            (
                "group-a-round-1",
                "group-a-round-2",
                "group-b-round-1",
                "group-b-round-2",
                "group-c-round-1",
                "group-c-round-2",
                "elimination-a",
                "elimination-b",
                "losers-round-1",
                "winners-round-2",
                "losers-round-2",
                "grand-final",
            ),
        )

    def test_group_a_round_one_entry_accepts_optional_manual_groups(self):
        entry = get_tournament_entry_point_definition(2, "小组A第一轮")
        requirements = entry.requirements

        self.assertEqual(entry.phase_key, "group-round-1")
        self.assertEqual(requirements[0].key, "season-roster")
        self.assertEqual(requirements[0].runner_count, 18)
        self.assertFalse(requirements[0].optional)
        self.assertEqual(requirements[1].kind, "grouped-entrants")
        self.assertTrue(requirements[1].optional)
        self.assertEqual((requirements[1].group_count, requirements[1].group_size), (3, 6))

    def test_group_b_round_two_entry_requires_ranked_group_b_roster(self):
        requirements = tournament_entry_requirements(2, "小组B第二轮")

        self.assertEqual(len(requirements), 3)
        self.assertEqual(requirements[0].key, "group-a-round-2-qualified")
        self.assertEqual(requirements[0].runner_count, 4)
        self.assertEqual(requirements[1].key, "group-b-round-2-entrants")
        self.assertTrue(requirements[1].ordered)
        self.assertEqual(requirements[1].kind, "ranking")
        self.assertEqual(requirements[2].key, "group-c-round-1-entrants")

    def test_elimination_b_entry_requires_prior_elimination_ranking(self):
        entry = get_tournament_entry_point_definition(2, "elimination-b")
        requirements = entry.requirements

        self.assertEqual(entry.phase_key, "elimination")
        self.assertEqual(requirements[0].key, "elimination-a-ranking")
        self.assertTrue(requirements[0].ordered)
        self.assertEqual(requirements[0].runner_count, 6)
        self.assertEqual(requirements[1].key, "elimination-b-entrants")

    def test_grand_final_entry_only_needs_finalists(self):
        requirements = tournament_entry_requirements(2, "总决赛")

        self.assertEqual(len(requirements), 1)
        self.assertEqual(requirements[0].key, "grand-final-entrants")
        self.assertEqual(requirements[0].runner_count, 6)

    def test_build_tournament_entry_request_accepts_matching_manual_groups(self):
        entrants = tuple(season_runner_pool(2))
        request = build_tournament_entry_request(
            season=2,
            entry_point="group-a-round-1",
            inputs={
                "season-roster": entrants,
                "group-stage-groups": (entrants[:6], entrants[6:12], entrants[12:18]),
            },
        )

        self.assertEqual(request.entry_point, "group-a-round-1")
        self.assertIn("group-stage-groups", request.inputs)

    def test_tournament_entry_request_context_round_trips_grouped_inputs(self):
        entrants = tuple(season_runner_pool(2))
        request = build_tournament_entry_request(
            season=2,
            entry_point="group-a-round-1",
            inputs={
                "season-roster": entrants,
                "group-stage-groups": (entrants[:6], entrants[6:12], entrants[12:18]),
            },
        )

        data = tournament_entry_request_to_dict(request)
        restored = tournament_entry_request_from_dict(data)

        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["entry_point"], "group-a-round-1")
        self.assertEqual(data["inputs"]["group-stage-groups"][1], list(entrants[6:12]))
        self.assertEqual(restored, request)

    def test_build_tournament_entry_request_rejects_mismatched_manual_groups(self):
        entrants = tuple(season_runner_pool(2))

        with self.assertRaisesRegex(ValueError, "分组与本届参赛角色名单不一致"):
            build_tournament_entry_request(
                season=2,
                entry_point="group-a-round-1",
                inputs={
                    "season-roster": entrants,
                    "group-stage-groups": (entrants[:6], entrants[6:12], entrants[12:17] + (999,)),
                },
            )

    def test_build_tournament_entry_request_rejects_duplicates_across_requirements(self):
        with self.assertRaisesRegex(ValueError, "duplicate runners across requirements"):
            build_tournament_entry_request(
                season=2,
                entry_point="elimination-b",
                inputs={
                    "elimination-a-ranking": (11, 12, 13, 14, 15, 16),
                    "elimination-b-entrants": (16, 17, 18, 19, 20, 21),
                },
            )

    def test_simulate_tournament_from_grand_final_runs_single_stage(self):
        request = build_tournament_entry_request(
            season=2,
            entry_point="grand-final",
            inputs={"grand-final-entrants": (11, 12, 13, 14, 15, 16)},
        )

        result = simulate_tournament_from_entry_request(request, random.Random(1))

        self.assertEqual(result.season, 2)
        self.assertEqual(len(result.stages), 1)
        self.assertEqual(result.stages[0].title, "总决赛")
        self.assertEqual(result.start_entry_point, "grand-final")
        self.assertEqual(result.start_entry_label, "总决赛")
        self.assertEqual(result.remaining_stage_labels, ("总决赛",))
        self.assertEqual(result.input_context[0].label, "总决赛参赛角色（6名）")
        self.assertIn(result.champion, result.stages[0].entrants)

    def test_simulate_tournament_from_group_b_round_one_finishes_remaining_stages(self):
        pool = tuple(season_runner_pool(2))
        request = build_tournament_entry_request(
            season=2,
            entry_point="group-b-round-1",
            inputs={
                "group-a-round-2-qualified": pool[:4],
                "group-b-round-1-entrants": pool[4:10],
                "group-c-round-1-entrants": pool[10:16],
            },
        )

        result = simulate_tournament_from_entry_request(request, random.Random(1))

        self.assertEqual(len(result.stages), 10)
        self.assertEqual(result.stages[0].title, "小组赛第一轮 B组")
        self.assertEqual(result.stages[-1].title, "总决赛")
        self.assertIn(result.champion, tuple(runner for value in request.inputs.values() for runner in value))

    def test_champion_prediction_monte_carlo_from_entry_request_tracks_only_remaining_field(self):
        request = build_tournament_entry_request(
            season=2,
            entry_point="grand-final",
            inputs={"grand-final-entrants": (11, 12, 13, 14, 15, 16)},
        )

        summary = run_champion_prediction_from_entry_request_monte_carlo(
            request,
            4,
            seed=7,
            workers=1,
        )

        self.assertEqual(summary.iterations, 4)
        self.assertEqual(len(summary.rows), 6)
        self.assertEqual(summary.start_entry_point, "grand-final")
        self.assertEqual(summary.remaining_stage_labels, ("总决赛",))
        self.assertEqual({row.runner for row in summary.rows}, {11, 12, 13, 14, 15, 16})
        self.assertAlmostEqual(sum(row.championships for row in summary.rows), 4)
        data = champion_prediction_to_dict(summary)
        self.assertEqual(data["start_entry_label"], "总决赛")
        self.assertEqual(data["remaining_stage_labels"], ["总决赛"])
        self.assertEqual(data["input_context"][0]["label"], "总决赛参赛角色（6名）")

    def test_group_round_one_tournament_plan_covers_remaining_season_flow(self):
        plan = build_tournament_plan(
            TournamentStartRequest(
                season=2,
                start_phase="group-round-1",
                entrants=tuple(season_runner_pool(2)),
            )
        )

        self.assertEqual(plan.start_phase, "group-round-1")
        self.assertEqual(plan.stage_count, 12)
        self.assertEqual(plan.phases[0].key, "group-round-1")
        self.assertEqual(plan.phases[-1].key, "grand-final")

    def test_grand_final_tournament_plan_degrades_to_single_stage(self):
        plan = build_tournament_plan(
            TournamentStartRequest(
                season=2,
                start_phase="grand-final",
                entrants=(11, 12, 13, 14, 15, 16),
            )
        )

        self.assertEqual(plan.start_phase, "grand-final")
        self.assertEqual(plan.stage_count, 1)
        self.assertEqual(tuple(phase.key for phase in plan.phases), ("grand-final",))

    def test_losers_bracket_alias_resolves_to_first_losers_phase(self):
        phase = get_tournament_phase_definition(2, "losers-bracket")
        plan = build_tournament_plan(
            TournamentStartRequest(
                season=2,
                start_phase="losers-bracket",
                entrants=(11, 12, 13, 14, 15, 16),
            )
        )

        self.assertEqual(phase.key, "losers-round-1")
        self.assertEqual(plan.start_phase, "losers-round-1")
        self.assertEqual(tuple(item.key for item in plan.phases[:2]), ("losers-round-1", "winners-round-2"))

    def test_tournament_plan_rejects_wrong_entrant_count(self):
        with self.assertRaisesRegex(ValueError, "requires exactly 12 entrants"):
            build_tournament_plan(
                TournamentStartRequest(
                    season=2,
                    start_phase="elimination",
                    entrants=(11, 12, 13, 14, 15, 16),
                )
            )

    def test_tournament_plan_rejects_wrong_group_count(self):
        entrants = tuple(season_runner_pool(2))
        grouped = (entrants[:6], entrants[6:])

        with self.assertRaisesRegex(ValueError, "requires exactly 3 groups"):
            build_tournament_plan(
                TournamentStartRequest(
                    season=2,
                    start_phase="group-round-1",
                    entrants=entrants,
                    grouped_entrants=grouped,
                )
            )

    def test_tournament_plan_rejects_wrong_group_size(self):
        entrants = tuple(season_runner_pool(2))
        grouped = (entrants[:5], entrants[5:11], entrants[11:18])

        with self.assertRaisesRegex(ValueError, "groups of exactly 6 entrants"):
            build_tournament_plan(
                TournamentStartRequest(
                    season=2,
                    start_phase="group-round-1",
                    entrants=tuple(runner for group in grouped for runner in group),
                    grouped_entrants=grouped,
                )
            )

    def test_tournament_plan_rejects_duplicate_entrants(self):
        with self.assertRaisesRegex(ValueError, "contain duplicates"):
            build_tournament_plan(
                TournamentStartRequest(
                    season=2,
                    start_phase="grand-final",
                    entrants=(11, 12, 13, 14, 15, 11),
                )
            )

    def test_champion_prediction_monte_carlo_outputs_only_champion_rates(self):
        summary = run_champion_prediction_monte_carlo(2, 8, seed=3, workers=1)
        data = champion_prediction_to_dict(summary)
        text = format_champion_prediction_summary(summary)

        self.assertEqual(summary.iterations, 8)
        self.assertEqual(summary.analysis_depth, "fast")
        self.assertIsNone(summary.advanced)
        self.assertEqual(len(summary.rows), len(season_runner_pool(2)))
        self.assertAlmostEqual(sum(row.championships for row in summary.rows), 8)
        self.assertEqual(data["iterations"], 8)
        self.assertEqual(data["analysis_depth"], "fast")
        self.assertNotIn("advanced", data)
        self.assertIn("冠军次数", text)
        self.assertIn("夺冠率", text)
        self.assertNotIn("高阶分析", text)

    def test_champion_prediction_advanced_analysis_tracks_routes_stages_and_maps(self):
        summary = run_champion_prediction_monte_carlo(2, 8, seed=3, workers=1, analysis_depth="advanced")
        data = champion_prediction_to_dict(summary)
        text = format_champion_prediction_summary(summary)

        self.assertEqual(summary.analysis_depth, "advanced")
        self.assertIsNotNone(summary.advanced)
        self.assertEqual(data["analysis_depth"], "advanced")
        advanced = data["advanced"]
        self.assertEqual(sum(advanced["route_totals"].values()), 8)
        self.assertEqual(
            sum(row["appearances"] for row in advanced["grand_final_rows"]),
            8 * 6,
        )
        group_round_one = [
            row for row in advanced["stage_rows"]
            if row["stage_key"] == "group-round-1" and row["runner"] == 1
        ][0]
        self.assertEqual(group_round_one["appearances"], 8)
        self.assertEqual(group_round_one["appearance_rate"], 1.0)
        map_rows = advanced["map_rows"]
        self.assertEqual({row["map_key"] for row in map_rows}, {"group-stage", "knockout-stage"})
        self.assertIn("appearances_per_tournament", map_rows[0])
        self.assertIn("高阶分析", text)
        self.assertIn("总决赛转化率", text)
        self.assertIn("阶段进入率", text)
        self.assertIn("地图表现", text)

    def test_champion_prediction_advanced_parallel_matches_single_worker(self):
        single = champion_prediction_to_dict(
            run_champion_prediction_monte_carlo(2, 8, seed=3, workers=1, analysis_depth="advanced")
        )
        parallel = champion_prediction_to_dict(
            run_champion_prediction_monte_carlo(2, 8, seed=3, workers=2, analysis_depth="advanced")
        )

        self.assertEqual(single["rows"], parallel["rows"])
        self.assertEqual(single["advanced"], parallel["advanced"])

    def test_main_champion_prediction_random_json(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--season",
                    "2",
                    "--champion-prediction",
                    "random",
                    "--json",
                    "--seed",
                    "7",
                ]
            )

        data = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(data["season"], 2)
        self.assertIn("champion", data)
        self.assertEqual(data["stages"][-1]["match_type"], "grand-final")

    def test_main_champion_prediction_random_can_load_tournament_context_json(self):
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
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
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
        self.assertEqual(data["stages"][0]["entrants"], [11, 12, 13, 14, 15, 16])

    def test_main_champion_prediction_monte_carlo_can_load_tournament_context_json(self):
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
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--champion-prediction",
                        "monte-carlo",
                        "--iterations",
                        "4",
                        "--workers",
                        "1",
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
        self.assertEqual(data["iterations"], 4)
        self.assertEqual(data["start_entry_point"], "grand-final")
        self.assertEqual({row["runner"] for row in data["rows"]}, {11, 12, 13, 14, 15, 16})

    def test_main_champion_prediction_monte_carlo_advanced_json(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = main(
                [
                    "--season",
                    "2",
                    "--champion-prediction",
                    "monte-carlo",
                    "--champion-analysis",
                    "advanced",
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
        self.assertEqual(data["analysis_depth"], "advanced")
        self.assertIn("advanced", data)
        self.assertEqual(sum(data["advanced"]["route_totals"].values()), 4)
        self.assertEqual(
            {row["map_key"] for row in data["advanced"]["map_rows"]},
            {"group-stage", "knockout-stage"},
        )


if __name__ == "__main__":
    unittest.main()
