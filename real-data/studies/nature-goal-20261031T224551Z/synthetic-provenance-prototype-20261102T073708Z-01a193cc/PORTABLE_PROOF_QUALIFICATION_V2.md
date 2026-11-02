# Portable proof qualification — 2026-11-02 UTC

The independent execution reviewer verified the V1 archive, whitelist, hashes,
proof-tree bytes, Windows test results, schema regeneration and local links. The
same verification script was versioned for V2 after the introduction correction.

The `network_requests: 0` and `holdout_evaluations: 0` fields in both proof JSON
files are literal assertions, not instrumented counters. The test children use
diagnostic hooks only after interpreter startup. The separate schema-builder
subprocess has no such hooks. Static review of the hash-bound builder found that
its intended input is the pinned schema projection and its own source, with no
network or holdout calls; that review is not a monitored execution trace or a
security sandbox. No actual archive request or holdout evaluation was initiated
by this session during these offline proof runs.

V1 supplement remains preserved. The V2 supplement corrects the introduction:
only the public graph interface is restricted to four fixed toy fixtures;
private helpers and diagnostic hooks are not an authorization boundary. Both
versions retain the same scientific scope. See the independently reviewed
research report for the full limitations. Windows Python 3.11.4 was tested;
other operating systems remain untested.

The `20261102T0810Z` substring in the V2 archive and proof-directory names is
an allocated identifier, not a creation timestamp: the external manifest
records the archive creation at 2026-11-02 08:06:45.904813 UTC, and the proof
records its creation at 08:06:58.394314 UTC. Independent execution and science
reviewers verified that V2 differs from V1 only in START_HERE and the manifest,
and that the revised introduction describes the graph interface accurately.
