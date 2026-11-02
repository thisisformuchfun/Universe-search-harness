# Gaia held-source explorer

This portable explorer shows the same 14 original held sources and public references from the dashboard snapshot generated 2026-11-02. Select a source in the list or 3D view; drag the sky view to rotate it. Distances are approximate inverse-parallax estimates, not distances with calibrated uncertainty. Filters operate on these 14 entries only.

This is a static snapshot. It does not include or connect to the originating private agent-activity feed, a live checkpoint monitor, or the Data plugin's product-owned shell. It cannot establish the current state of any agent or establish a black-hole discovery.

Install Node.js 22 or later, then:

```sh
npm ci
npm run dev
```

Open the local URL printed by Vite. `npm run build` creates a deployable `dist/` directory. `src/SpaceView.jsx`, its CSS, geometry helpers, and `src/snapshot.json` are the dashboard-specific source and dated data. The app shell here is a small standalone wrapper. The source IDs are strings so the browser cannot round Gaia identifiers.

See [the literature review](../public-review/README.md) and the [research handoff](../real-data/START_HERE.md) for evidence and limitations.
