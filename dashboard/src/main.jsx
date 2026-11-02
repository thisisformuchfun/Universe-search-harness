import React from "react";
import { createRoot } from "react-dom/client";
import { SpaceView } from "./SpaceView.jsx";
import { nominalDistanceLightYears } from "./space-geometry.js";
import snapshot from "./snapshot.json";
import "./style.css";

function App() {
  const [filter, setFilter] = React.useState("all");
  const [search, setSearch] = React.useState("");
  const [distance, setDistance] = React.useState("");
  const limit = Number(distance);
  const validDistance = distance.trim() !== "" && Number.isFinite(limit) && limit > 0;
  const invalidDistance = distance.trim() !== "" && !validDistance;
  const visible = snapshot.rows.filter((row) => {
    const ly = nominalDistanceLightYears(row);
    const published = row.status === "PREVIOUSLY_STUDIED_CANDIDATE_NOT_NEW";
    return (filter === "all" || (filter === "published" ? published : !published))
      && row.source_id.includes(search.trim())
      && (!validDistance || (ly !== null && ly <= limit));
  });
  return <main className="page">
    <header className="header"><span className="kicker">GAIA DR3 · RESEARCH SNAPSHOT</span><h1>Held-source explorer</h1><p>Inspect the measurements, evidence and open questions for 14 historical anomalies.</p></header>
    <div className="notice"><strong>Static snapshot · not a live agent feed.</strong> The source notes and literature reviews have different dates. No new black hole is confirmed by these records.</div>
    <section className="panel" aria-label="Source explorer">
      <SpaceView rows={snapshot.rows} visibleRows={visible} filter={filter} setFilter={setFilter} search={search} setSearch={setSearch} distance={distance} setDistance={setDistance} invalidDistance={invalidDistance} matrixAsOf={snapshot.matrix_as_of} statusAsOf={snapshot.matrix_as_of} bridgeUrl={null} warning={null} />
    </section>
    <footer>Source details are a dated review, not a complete sky survey. See the repository README for the research handoff and reproducibility notes.</footer>
  </main>;
}

createRoot(document.getElementById("root")).render(<App />);
