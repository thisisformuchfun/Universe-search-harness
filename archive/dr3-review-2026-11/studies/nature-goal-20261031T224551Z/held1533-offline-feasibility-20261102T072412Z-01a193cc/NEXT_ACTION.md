# Next action and stopping boundary

The current single-stack pixels and headers cannot settle whether the PS1
catalog detection is independent of the stack, resolve the putative source,
or attribute LAMOST fibre light. No further same-stack request is scheduled.
Exact exposure/CCD lineage with pixel-level inclusion, a validated local PSF
and noise model, or independent resolved/phase-resolved observations would
address distinct limitations; any new adopted scientific criteria require the
previously specified proposal, independent review and user approval.

A local, read-only regression check for the corrected inventory is:

```powershell
Push-Location 'C:\gogogo\universe search harness\blackhole search\astra-20261031T2113Z-01a193cc\studies\nature-goal-20261031T224551Z\held1533-offline-feasibility-20261102T072412Z-01a193cc'
try { & 'C:\gogogo\universe search harness\blackhole search\astra-20261031T2113Z-01a193cc\.venv-pixel-descriptive\Scripts\python.exe' -B -m unittest test_pixel_bounds test_wcs_coords -v } finally { Pop-Location }
```

Reproduction of the inventory itself needs a fresh sibling directory as
explained in `REPRODUCIBILITY_V2.md`. Do not reset or recreate the quarantined
historical holdout. No unattended work has been scheduled.
