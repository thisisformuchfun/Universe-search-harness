# Next action

The completed Zhou–Gu paper comparison does not clear novelty for any of the
14. A calibrated, source-attributed RV series at separated phases could test
the proposed orbit and scan-angle alternatives; success requires uncertainty-aware
phase coverage and calibration. Validated resolved-light data could constrain
blending and luminous-neighbor alternatives, but an image alone does not prove
orbital motion or companion type. A single mean RV, another catalogue nonmatch
or a ranking score is insufficient.
Choose a specific source and public route from the [source matrix](../held14-rv-recovery-20261102T0622Z-01a193cc/SOURCE_MATRIX.md),
then freeze and independently review the bounded acquisition before running it.
No observation or job is scheduled.

To repeat the latest offline synthetic fixed-width regressions on the original
PC without touching the saved result or scientific holdout:

```powershell
Set-Location -LiteralPath 'C:\gogogo\universe search harness\blackhole search\astra-20261031T2113Z-01a193cc\studies\nature-goal-20261031T224551Z\zhou-mrt-20261102T1041Z-01a193cc'
& 'C:\gogogo\universe search harness\blackhole search\astra-20261031T2113Z-01a193cc\.venv-fits-study\Scripts\python.exe' -B -m unittest -v test_compare_table_v3
```

The scientific holdout remains owned by `astra-20261031T2113Z-01a193cc` and
quarantined `DO_NOT_EVALUATE`. Do not recreate or reassign it.
