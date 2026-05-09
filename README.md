# Wuthering Waves Cubie Derby Monte Carlo

Python Monte Carlo simulator for Cubie Derby race outcomes. It ports the original MATLAB script into a reusable CLI and simulation module.

## Quick Start

Run the current finals-lower-half preset:

```powershell
python cubie_derby.py -n 100000 --preset 4 --seed 42
```

Use a custom known track environment. Positions are zero-based, and runners in the same position are ordered from left to right:

```powershell
python cubie_derby.py -n 100000 --track-length 25 --start "1:10;2:4,3;3:8" --runners 3 4 8 10 --seed 42
```

Start all selected runners in one cell with a freshly randomized stack order in every simulated race:

```powershell
python cubie_derby.py -n 100000 --track-length 25 --start "0:*" --runners 3 4 8 10 --seed 42
```

Use `--initial-order start` if the first-round action order should follow that randomized stack order.

```powershell
python cubie_derby.py -n 100000 --track-length 25 --start "0:*" --runners 3 4 8 10 --initial-order start
```

Print machine-readable output:

```powershell
python cubie_derby.py -n 10000 --preset 4 --json
```

Trace one race for rule debugging:

```powershell
python cubie_derby.py --preset 4 --seed 2 --trace
```

## Built-In Presets

- `1`: random first-round order, random start stack, 22-length track.
- `2`: first-round order follows random start stack, 22-length track.
- `3`: fixed A-group upper-half start/order from the MATLAB script, 22-length track.
- `4`: fixed finals lower-half start with random first-round order, 25-length track.
- `5`: fixed A-group lower-half start/order from the MATLAB script, 25-length track.

## Output Columns

- `win_rate`: estimated first-place probability.
- `avg_rank`: lower is better.
- `rank_var`: ranking volatility.
- `gap/race`: MATLAB-compatible champion margin contribution averaged across all races.
- `gap/when_win`: average winner margin only among races won by that runner.

## Tests

```powershell
python -m unittest discover -s tests
```
