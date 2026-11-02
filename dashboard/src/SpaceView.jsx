import React from "react";
import { LIGHT_YEARS_PER_PARSEC, nominalDistanceLightYears, positionFromAstrometry, projectPosition } from "./space-geometry.js";
import "./space-view.css";

const isPublished = (row) => row?.status === "PREVIOUSLY_STUDIED_CANDIDATE_NOT_NEW";
const cleanText = (value) => String(value || "Not available in this review.").replace(/^(U\.\s*|P:\s*)/, "").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/`/g, "");
const dateTime = (s) => {
  const d = new Date(s);
  return !s || Number.isNaN(d.getTime()) ? "date unavailable" : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
};
const fmt = (n, digits = 2) => Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: digits }) : "—";

function PublicReview({ review }) {
  if (!review) return <section className="public-review"><h5>Public references and contacts</h5><p>Publication checks are not available for this source in the dashboard snapshot.</p></section>;
  return <section className="public-review">
    <div className="public-review-heading"><div><span className="space-evidence-label">PUBLIC RESEARCH</span><h5>References and contacts</h5></div><span>Reviewed {dateTime(review.reviewed_utc)}</span></div>
    <p className="public-review-intro">Object-specific matches are shown below. These checks do not cover every publication or establish novelty.</p>
    {review.matches.length ? <div className="public-matches">{review.matches.map((item) => <article className="public-match" key={`${item.kind}-${item.url}`}>
      <span className="public-match-kind">{item.kind}</span>
      <a className="public-match-title" href={item.url} target="_blank" rel="noreferrer">{item.title} ↗</a>
      <p>{item.detail}</p>
      {item.dataset_url && <a className="public-dataset" href={item.dataset_url} target="_blank" rel="noreferrer">Public dataset ↗</a>}
      {item.contact && <div className="public-contact"><span><strong>{item.contact.name}</strong> · {item.contact.role}</span><span><a href={`mailto:${item.contact.email}`}>{item.contact.email}</a> <a className="public-contact-source" href={item.contact.source_url} target="_blank" rel="noreferrer">Contact source ↗</a></span></div>}
    </article>)}</div> : <div className="public-no-match">No object-specific research paper or spectral-model result was verified in these literature checks. That does not mean none exists.</div>}
    {review.cross_id && <div className="public-cross-id"><strong>Gaia cross-identification: {review.cross_id.designation}</strong><span>Gaia's positional crossmatch reports a {fmt(review.cross_id.separation_arcsec, 3)}″ separation.{review.cross_id.number_of_mates > 0 ? ` It reports ${review.cross_id.number_of_mates} other Gaia mate, so the match may be shared.` : " A crossmatch alone does not establish a companion or rule out blended light."}</span><a href={review.cross_id.lookup_url} target="_blank" rel="noreferrer">Search this 2MASS ID in SIMBAD ↗</a></div>}
    <details className="public-checks"><summary>See the four literature checks</summary><div>{review.checks.map((check) => <div className="public-check" key={check.title}><a href={check.url} target="_blank" rel="noreferrer">{check.title} ↗</a><span>{check.result}</span></div>)}<div className="public-check"><strong>Li et al. 2025 XP parent dataset</strong><span>{review.xp_status}</span></div></div></details>
    <p className="public-review-limit">{review.limitations}</p>
  </section>;
}

function SkyPlot({ rows, selectedId, onSelect }) {
  const [orientation, setOrientation] = React.useState({ yaw: -0.65, pitch: 0.55, zoom: 1 });
  const drag = React.useRef(null);
  const moved = React.useRef(false);
  const project = (p) => projectPosition(p, orientation.yaw, orientation.pitch, orientation.zoom);
  const rings = [500, 1000, 1500, 2000].map((radius) => {
    const points = Array.from({ length: 97 }, (_, i) => {
      const a = i * Math.PI * 2 / 96;
      const p = project({ x: radius * Math.cos(a), y: radius * Math.sin(a), z: 0 });
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    }).join(" ");
    const label = project({ x: radius, y: 0, z: 0 });
    return <g key={radius}><polyline points={points} className="space-grid-ring" /><text className="space-ring-label" x={label.x + 5} y={label.y - 7}>{Math.round(radius * LIGHT_YEARS_PER_PARSEC).toLocaleString()} ly</text></g>;
  });
  const origin = project({ x: 0, y: 0, z: 0 });
  const axes = [
    { name: "X", point: { x: 2150, y: 0, z: 0 } },
    { name: "Y", point: { x: 0, y: 2150, z: 0 } },
    { name: "Z", point: { x: 0, y: 0, z: 2150 } },
  ].map((axis) => ({ ...axis, at: project(axis.point) }));
  const plotted = rows.map((row) => ({ row, point: positionFromAstrometry(row.ra_deg, row.dec_deg, row.parallax_mas) }))
    .filter((item) => item.point).map((item) => ({ ...item, at: project(item.point) })).sort((a, b) => a.at.depth - b.at.depth);
  const selected = plotted.find((item) => item.row.source_id === selectedId);

  const pointerDown = (e) => {
    if (e.button !== 0) return;
    moved.current = false;
    drag.current = { x: e.clientX, y: e.clientY, yaw: orientation.yaw, pitch: orientation.pitch };
  };
  const pointerMove = (e) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) < 4 && !moved.current) return;
    moved.current = true;
    if (!e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.setPointerCapture(e.pointerId);
    setOrientation((s) => ({ ...s, yaw: d.yaw + dx * 0.008, pitch: Math.max(-1.4, Math.min(1.4, d.pitch + dy * 0.008)) }));
  };
  const choose = (row) => { if (!moved.current) onSelect(row.source_id); };

  return <div className="space-stage-wrap">
    <div className="space-stage-heading"><div><span className="space-stage-kicker">SUN-CENTERED VIEW</span><strong>Explore the candidates</strong></div><span className="space-stage-hint">Drag to rotate</span></div>
    <svg className="space-stage" viewBox="0 0 800 520" role="group" aria-label="Interactive three-dimensional positions of the held Gaia sources" onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <defs><radialGradient id="space-sun-glow"><stop offset="0" stopColor="#b9e5ff" stopOpacity=".42" /><stop offset="1" stopColor="#b9e5ff" stopOpacity="0" /></radialGradient></defs>
      <g>{rings}</g>
      {axes.map((a) => <g key={a.name}><line className="space-axis" x1={origin.x} y1={origin.y} x2={a.at.x} y2={a.at.y} /><text className="space-axis-label" x={a.at.x} y={a.at.y}>{a.name}</text></g>)}
      {selected && <line className="space-selected-line" x1={origin.x} y1={origin.y} x2={selected.at.x} y2={selected.at.y} />}
      <circle cx={origin.x} cy={origin.y} r="24" fill="url(#space-sun-glow)" /><circle cx={origin.x} cy={origin.y} r="3.5" fill="#d8efff" /><text className="space-sun-label" x={origin.x + 9} y={origin.y - 7}>SUN</text>
      {plotted.map(({ row, at }) => <g key={row.source_id} className={`space-mark ${isPublished(row) ? "published" : "unresolved"} ${row.source_id === selectedId ? "selected" : ""}`} role="button" tabIndex="0" aria-label={`Select Gaia source ${row.source_id}`} aria-pressed={row.source_id === selectedId} onClick={() => choose(row)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(row.source_id); } }}>
        <title>Gaia DR3 {row.source_id} · {isPublished(row) ? "previously published" : "novelty unresolved"}</title>
        <circle className="space-mark-hit" cx={at.x} cy={at.y} r="16" />
        <circle className="space-mark-halo" cx={at.x} cy={at.y} r={row.source_id === selectedId ? 14 : 8} />
        <circle className="space-mark-core" cx={at.x} cy={at.y} r={row.source_id === selectedId ? 5 : 3.5} />
      </g>)}
    </svg>
    <div className="space-stage-footer"><div className="space-legend"><span><i className="space-key unresolved" />Novelty unresolved</span><span><i className="space-key published" />Previously published</span><span><i className="space-key sun" />Sun</span></div><div className="space-view-controls"><button onClick={() => setOrientation((s) => ({ ...s, zoom: Math.max(0.65, s.zoom - 0.2) }))} aria-label="Zoom out">−</button><button onClick={() => setOrientation((s) => ({ ...s, zoom: Math.min(1.65, s.zoom + 0.2) }))} aria-label="Zoom in">+</button><button onClick={() => setOrientation({ yaw: -0.65, pitch: 0.55, zoom: 1 })}>Reset view</button></div></div>
    <div className="space-stage-note">Each ring is 1,631 light-years (500 pc) farther out in the equatorial plane. The Solar System is too small to show at this scale.</div>
  </div>;
}

export function SpaceView({ rows, visibleRows, filter, setFilter, search, setSearch, distance, setDistance, invalidDistance, matrixAsOf, statusAsOf, bridgeUrl, warning }) {
  const [selectedId, setSelectedId] = React.useState(rows[0]?.source_id || null);
  const visible = visibleRows;
  const selected = visible.find((row) => row.source_id === selectedId) || visible[0] || null;
  const point = selected && positionFromAstrometry(selected.ra_deg, selected.dec_deg, selected.parallax_mas);
  const distances = rows.map(nominalDistanceLightYears).filter(Number.isFinite);
  const nearest = distances.length ? Math.round(Math.min(...distances) / 10) * 10 : null;
  const farthest = distances.length ? Math.round(Math.max(...distances) / 10) * 10 : null;
  const setSelection = (id) => setSelectedId(id);
  return <div className="space-explorer" data-reviewed-rows>
    <div className="space-intro"><div><span className="space-eyebrow">ORIGINAL HELD SOURCES</span><h3>One sky, 14 open reviews</h3><p>Select a point or a source to see the measurements, risks, and next useful test.</p></div><div className="space-intro-status"><span className="space-intro-dot" />Review status recorded {dateTime(statusAsOf || matrixAsOf)}</div></div>
    <div className="space-scope"><strong>{nearest !== null ? `About ${fmt(nearest, 0)}–${fmt(farthest, 0)} light-years from the Sun` : "Distances unavailable"}</strong><span>These are 14 held sources from a ranked 500-orbit Gaia snapshot, not a complete sky search at any distance.</span></div>
    {warning && <p className="space-warning">{warning}</p>}
    <div className="space-workbench">
      <SkyPlot rows={visible} selectedId={selected?.source_id} onSelect={setSelection} />
      <div className="space-sidebar">
        <div className="space-sidebar-head"><div><span className="space-sidebar-kicker">SOURCE INDEX</span><h4>Review queue <span>{visible.length} / {rows.length}</span></h4></div></div>
        <label className="space-search"><span className="space-search-icon" aria-hidden="true">⌕</span><span className="space-sr-only">Search Gaia source ID</span><input value={search} onChange={(e) => setSearch(e.target.value)} inputMode="numeric" placeholder="Search Gaia source ID" /></label>
        <div className="space-filters" aria-label="Filter source status">{[["all", "All"], ["unresolved", "Unresolved"], ["published", "Published"]].map(([id, label]) => <button key={id} aria-pressed={filter === id} onClick={() => setFilter(id)}>{label}</button>)}</div>
        <div className="space-distance-filter"><label>Within (light-years)<input type="number" min="0.01" step="any" inputMode="decimal" value={distance} onChange={(e) => setDistance(e.target.value)} aria-invalid={invalidDistance || undefined} placeholder="Any distance" /></label><button onClick={() => setDistance("10")}>10 ly</button><button onClick={() => setDistance("")}>Clear</button><p>{invalidDistance ? "Enter a positive distance." : "Filters this 14-source snapshot; it does not search the sky."}</p></div>
        <div className="space-source-list">{visible.length ? visible.map((row) => <button key={row.source_id} className={`space-source ${selected?.source_id === row.source_id ? "active" : ""}`} aria-pressed={selected?.source_id === row.source_id} onClick={() => setSelection(row.source_id)}><span className={`space-list-dot ${isPublished(row) ? "published" : ""}`} /><span className="space-source-main"><strong>{row.source_id}</strong><small>{isPublished(row) ? "Previously published" : "Novelty unresolved"} <span>·</span> ≈ {fmt(nominalDistanceLightYears(row), 0)} ly</small></span><span className="space-chevron" aria-hidden="true">›</span></button>) : <p className="space-no-results">No sources in this 14-source snapshot match these filters. This is not evidence that the region is empty.</p>}</div>
      </div>
    </div>
    <p className="space-distance-caveat"><strong>Position is approximate.</strong> Distance is 1,000 ÷ Gaia NSS parallax in milliarcseconds, with no zero-point correction or probabilistic distance model. Measurement errors and systematics are not shown as 3D error bars.</p>
    {selected ? <div className="space-detail" aria-live="polite">
      <div className="space-detail-header"><div><span className="space-eyebrow">SELECTED SOURCE</span><h4>Gaia DR3 <span>{selected.source_id}</span></h4></div><span className={`space-status-pill ${isPublished(selected) ? "published" : ""}`}>{isPublished(selected) ? "Previously published candidate" : "Novelty unresolved"}</span></div>
      <div className="space-facts"><div><span>Approximate distance</span><strong>{point ? `${fmt(point.distance * LIGHT_YEARS_PER_PARSEC, 0)} light-years` : "Unavailable"}</strong><small>{point ? `≈ ${fmt(point.distance, 0)} pc` : ""}</small></div><div><span>Gaia period</span><strong>{fmt(selected.period_days)} days</strong><small>NSS orbital solution</small></div><div><span>Parallax</span><strong>{fmt(selected.parallax_mas, 3)} ± {fmt(selected.parallax_error_mas, 3)} mas</strong><small>Gaia NSS measurement</small></div><div><span>Sky position</span><strong>{fmt(selected.ra_deg, 2)}°, {fmt(selected.dec_deg, 2)}°</strong><small>RA, declination</small></div></div>
      <div className="space-evidence-grid"><div><span className="space-evidence-label">WHAT THE REVIEW FOUND</span><p>{cleanText(selected.literature_measurement)}</p></div><div><span className="space-evidence-label">WHAT COULD AFFECT IT</span><p>{cleanText(selected.material_risk)}</p></div><div className="space-next"><span className="space-evidence-label">NEXT USEFUL TEST</span><p>{cleanText(selected.next_measurement)}</p></div></div>
      {selected.later_followup && <p className="space-later"><strong>Later follow-up · {dateTime(selected.later_followup_as_of)}</strong><br />{selected.later_followup}</p>}
      <details className="space-extra"><summary>Completed Gaia-ESO lookup</summary><p>The review matrix records zero rows for all 14 fixed-position Gaia-ESO DR5.1 searches under the recorded query conditions. This result concerns that particular survey search; it does not rule out other observations or establish novelty.</p></details>
      {selected.xp_blend && <details className="space-extra"><summary>Gaia XP blending quality</summary><p>Blending was flagged in BP {selected.xp_blend.bp_blended} of {selected.xp_blend.bp_total} spectral transits and RP {selected.xp_blend.rp_blended} of {selected.xp_blend.rp_total}; reviewed {dateTime(selected.xp_blend.as_of)}. These flags indicate possible blended light, not a confirmed companion or a failed orbit. BP and RP counts are not independent epochs, and zero flags do not rule out contamination. <a href="https://gaia.aip.de/metadata/gaiadr3/xp_summary/" target="_blank" rel="noreferrer">Field definitions ↗</a></p></details>}
      <PublicReview review={selected.public_review} />
      <div className="space-detail-footer"><span>Review notes from {dateTime(matrixAsOf)}; later work may add to them.</span><span>{bridgeUrl && <a href={`${bridgeUrl}/matrix`} target="_blank" rel="noreferrer">Full source matrix ↗</a>}{isPublished(selected) && <a href="https://arxiv.org/html/2610.34715v1" target="_blank" rel="noreferrer">Published study ↗</a>}{bridgeUrl && <a href={`${bridgeUrl}/queue`} target="_blank" rel="noreferrer">Latest review queue ↗</a>}</span></div>
    </div> : <div className="space-detail-empty">Clear a filter to inspect the sources in this snapshot.</div>}
    <p className="space-bottom-note">All objects in this view are held for review. A missing literature match does not establish novelty or a black-hole discovery.</p>
  </div>;
}
