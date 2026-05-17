"""NPC behaviour and Season 2 special cells tests.

Split from the original monolithic tests/test_cubie_derby.py to
make selective runs and code review tractable. The shared
imports and helpers (fake RNGs, argparse_namespace fixture, etc.)
live in tests/_shared.py.
"""
from __future__ import annotations

import unittest

from tests._shared import *  # noqa: F401,F403  (test fixtures)


class NpcTests(unittest.TestCase):
    def test_npc_only_participates_in_ranking_after_action(self):
        grid = {13: [3], 14: [6], 31: [-1]}
        progress = {3: 13, 6: 14, -1: 31}

        self.assertEqual(rank_scope((3, 6), progress, include_npc=False), (3, 6))
        self.assertEqual(current_rank(rank_scope((3, 6), progress, False), progress, grid), [6, 3])
        self.assertEqual(rank_scope((3, 6), progress, include_npc=True), (3, 6, -1))
        self.assertEqual(current_rank(rank_scope((3, 6), progress, True), progress, grid), [-1, 6, 3])

    def test_season_two_default_rules(self):
        args = argparse_namespace(
            season=2,
            runners=["3", "4", "8", "10"],
            track_length=None,
            start="0:*",
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.track_length, 32)
        self.assertTrue(config.npc_enabled)
        self.assertEqual(config.forward_cells, season_rules(2)["forward_cells"])
        self.assertEqual(config.forward_cells, frozenset({3, 11, 16, 23}))
        self.assertEqual(config.backward_cells, frozenset({10, 28}))
        self.assertEqual(config.shuffle_cells, frozenset({6, 20}))

    def test_season_two_group_match_type_uses_group_stage_map(self):
        args = argparse_namespace(
            season=2,
            match_type="group-round-1",
            runners=["11", "12", "13", "14", "15", "16"],
            start=None,
            track_length=None,
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.match_type, "group-round-1")
        self.assertEqual(config.map_label, "小组赛阶段地图")
        self.assertEqual(config.forward_cells, frozenset({3, 11, 16, 23}))
        self.assertEqual(config.backward_cells, frozenset({10, 28}))
        self.assertEqual(config.shuffle_cells, frozenset({6, 20}))

    def test_season_two_knockout_match_type_uses_knockout_stage_map(self):
        args = argparse_namespace(
            season=2,
            match_type="elimination",
            runners=["11", "12", "13", "14", "15", "16"],
            start=None,
            track_length=None,
            initial_order=None,
        )

        config = build_config_from_args(args)

        self.assertEqual(config.match_type, "elimination")
        self.assertEqual(config.map_label, "淘汰赛阶段地图")
        self.assertEqual(config.forward_cells, frozenset({4, 10, 20}))
        self.assertEqual(config.backward_cells, frozenset({16, 26, 30}))
        self.assertEqual(config.shuffle_cells, frozenset({6, 14, 23}))

    def test_season_two_forward_cell_moves_group_one_more(self):
        config = RaceConfig(
            runners=(3,),
            track_length=32,
            start_grid={0: (3,)},
            season=2,
            forward_cells=frozenset({3}),
        )
        grid = {0: [3]}
        progress = {3: 0}

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            total_steps=3,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 4)
        self.assertEqual(progress[3], 4)
        self.assertEqual(grid[4], [3])

    def test_season_two_backward_cell_moves_group_back_one(self):
        config = RaceConfig(
            runners=(3,),
            track_length=32,
            start_grid={8: (3,)},
            season=2,
            backward_cells=frozenset({10}),
        )
        grid = {8: [3]}
        progress = {3: 8}

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            total_steps=2,
            rng=random.Random(1),
        )

        self.assertEqual(progress[3], 9)
        self.assertEqual(grid[9], [3])

    def test_luuk_herssen_turns_forward_cell_into_four_forward_steps(self):
        config = RaceConfig(
            runners=(14,),
            track_length=32,
            start_grid={0: (14,)},
            season=2,
            forward_cells=frozenset({3}),
        )
        grid = {0: [14]}
        progress = {14: 0}

        new_progress = move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=14,
            total_steps=3,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 7)
        self.assertEqual(progress[14], 7)
        self.assertEqual(grid[7], [14])

    def test_luuk_herssen_turns_backward_cell_into_two_backward_steps(self):
        config = RaceConfig(
            runners=(14,),
            track_length=32,
            start_grid={8: (14,)},
            season=2,
            backward_cells=frozenset({10}),
        )
        grid = {8: [14]}
        progress = {14: 8}

        move_single_runner(
            grid=grid,
            progress=progress,
            config=config,
            player=14,
            total_steps=2,
            rng=random.Random(1),
        )

        self.assertEqual(progress[14], 8)
        self.assertEqual(grid[8], [14])

    def test_luuk_herssen_does_not_enhance_special_cell_when_carried(self):
        config = RaceConfig(
            runners=(12, 14, 16),
            track_length=32,
            start_grid={21: (12, 14, 16)},
            season=2,
            forward_cells=frozenset({23}),
        )
        grid = {21: [12, 14, 16]}
        progress = {12: 21, 14: 21, 16: 21}

        new_progress = move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=16,
            idx_in_cell=2,
            total_steps=2,
            rng=random.Random(1),
        )

        self.assertEqual(new_progress, 24)
        self.assertEqual(progress[14], 24)
        self.assertEqual(grid[24], [12, 14, 16])
        self.assertNotIn(27, grid)

    def test_season_two_shuffle_cell_randomizes_arriving_group(self):
        config = RaceConfig(
            runners=(1, 2, 3, 4),
            track_length=32,
            start_grid={5: (1, 2, 3, 4)},
            season=2,
            shuffle_cells=frozenset({6}),
        )
        grid = {5: [1, 2, 3, 4]}
        progress = {1: 5, 2: 5, 3: 5, 4: 5}

        move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=4,
            idx_in_cell=3,
            total_steps=1,
            rng=random.Random(1),
        )

        self.assertCountEqual(grid[6], [1, 2, 3, 4])
        self.assertNotEqual(grid[6], [1, 2, 3, 4])

    def test_npc_moves_backward_and_stays_rightmost(self):
        grid = {30: [3]}
        progress = {3: 30}
        config = RaceConfig(runners=(3,), track_length=32, start_grid={30: (3,)})

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=random.Random(1),
            trace=False,
        )

        self.assertEqual(npc_progress, 30)
        self.assertEqual(grid[30], [3, -1])
        self.assertEqual(progress[-1], 30)

    def test_npc_carries_runners_it_passes_with_remaining_steps(self):
        grid = {0: [-1], 31: [3]}
        progress = {-1: 0, 3: 31}
        config = RaceConfig(runners=(3,), track_length=32, start_grid={31: (3,)})

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=FixedDiceRandom(random_value=0.1, dice_value=2),
            trace=False,
        )

        self.assertEqual(npc_progress, 30)
        self.assertEqual(progress[-1], 30)
        self.assertEqual(progress[3], 30)
        self.assertEqual(grid[30], [3, -1])
        self.assertNotIn(31, grid)

    def test_npc_carrying_group_enters_next_cell_from_left(self):
        grid = {
            19: [16, -1],
            18: [15, 13],
            17: [11],
        }
        progress = {-1: 19, 16: 19, 15: 18, 13: 18, 11: 17}
        config = RaceConfig(runners=(11, 13, 15, 16), track_length=32, start_grid={})

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=19,
            rng=FixedDiceRandom(random_value=0.1, dice_value=3),
            trace=False,
        )

        self.assertEqual(npc_progress, 16)
        self.assertNotIn(19, grid)
        self.assertNotIn(18, grid)
        self.assertNotIn(17, grid)
        self.assertEqual(grid[16], [16, 15, 13, 11, -1])
        self.assertEqual(progress[16], 16)
        self.assertEqual(progress[15], 16)
        self.assertEqual(progress[13], 16)
        self.assertEqual(progress[11], 16)

    def test_npc_does_not_carry_runners_already_stacked_before_first_action_round(self):
        grid = {0: [3, -1], 31: [4]}
        progress = {3: 0, 4: 31, -1: 0}
        config = RaceConfig(runners=(3, 4), track_length=32, start_grid={})

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=FixedDiceRandom(random_value=0.1, dice_value=2),
            trace=False,
            ignore_waiting_stack=True,
        )

        self.assertEqual(npc_progress, 30)
        self.assertEqual(progress[-1], 30)
        self.assertEqual(progress[3], 0)
        self.assertEqual(progress[4], 30)
        self.assertEqual(grid[0], [3])
        self.assertEqual(grid[30], [4, -1])

    def test_npc_triggers_fixed_backward_cell_after_landing(self):
        config = RaceConfig(
            runners=(3,),
            track_length=32,
            start_grid={0: (3,)},
            season=2,
            backward_cells=frozenset({28}),
        )
        grid: dict[int, list[int]] = {}
        progress = {-1: 0}

        npc_progress = move_npc(
            grid=grid,
            progress=progress,
            config=config,
            npc_progress=0,
            rng=FixedDiceRandom(random_value=0.1, dice_value=4),
            trace=False,
        )

        self.assertEqual(npc_progress, 27)
        self.assertEqual(progress[-1], 27)
        self.assertNotIn(28, grid)
        self.assertEqual(grid[27], [-1])

    def test_npc_stays_rightmost_after_shuffle_cell(self):
        config = RaceConfig(
            runners=(1, 2, 3),
            track_length=32,
            start_grid={5: (1, 2, 3), 6: (-1,)},
            season=2,
            shuffle_cells=frozenset({6}),
        )
        grid = {5: [1, 2, 3], 6: [-1]}
        progress = {1: 5, 2: 5, 3: 5}

        move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            idx_in_cell=2,
            total_steps=1,
            rng=random.Random(1),
        )

        self.assertEqual(grid[6][-1], -1)
        self.assertCountEqual(grid[6], [1, 2, 3, -1])

    def test_shuffle_cell_excludes_npc_from_shuffle_pool(self):
        config = RaceConfig(
            runners=(1, 2, 3),
            track_length=32,
            start_grid={5: (1, 2, 3), 6: (-1,)},
            season=2,
            shuffle_cells=frozenset({6}),
        )
        grid = {5: [1, 2, 3], 6: [-1]}
        progress = {1: 5, 2: 5, 3: 5, -1: 6}
        rng = RecordingShuffleRandom()

        move_runner_with_left_side(
            grid=grid,
            progress=progress,
            config=config,
            player=3,
            idx_in_cell=2,
            total_steps=1,
            rng=rng,
        )

        self.assertEqual(rng.shuffle_inputs, [[1, 2, 3]])
        self.assertEqual(grid[6], [3, 2, 1, -1])

    def test_npc_stays_when_position_is_not_less_than_last_runner(self):
        grid = {5: [3], 12: [4], 30: [-1]}
        progress = {3: 5, 4: 12}

        npc_progress = settle_npc_end_of_round(
            grid=grid,
            progress=progress,
            runners=(3, 4),
            npc_progress=-2,
            track_length=32,
            trace=False,
        )

        self.assertEqual(npc_progress, -2)
        self.assertEqual(grid[30], [-1])
        self.assertNotIn(-1, grid.get(0, []))

    def test_npc_returns_to_start_when_position_is_less_than_last_runner(self):
        grid = {21: [-1], 22: [3], 25: [4]}
        progress = {3: 22, 4: 25}

        npc_progress = settle_npc_end_of_round(
            grid=grid,
            progress=progress,
            runners=(3, 4),
            npc_progress=21,
            track_length=32,
            trace=False,
        )

        self.assertEqual(npc_progress, 0)
        self.assertEqual(grid[0], [-1])
        self.assertNotIn(-1, grid.get(21, []))


if __name__ == "__main__":
    unittest.main()
