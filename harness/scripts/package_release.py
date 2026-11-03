"""Create a separately named source ZIP from an allowlist, never overwrite one."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

TOP_FILES = {"AGENTS.md", "README.md", "LICENSE", "pyproject.toml", "requirements.lock"}
SOURCE_SUFFIXES = {"harness2": {".py"}, "tests": {".py"}, "scripts": {".py"}, "docs": {".md"}, "policy": {".json"}}


def package(root, output):
    root = Path(root).resolve()
    output = Path(output)
    if output.name == "Universe_Search_Harness_Real_Data_v1.zip":
        raise ValueError("Reserve the original baseline filename; choose a reviewed-patch name")
    pilot = root / "data/pilot"
    snapshot = json.loads((pilot / "SNAPSHOT_MANIFEST.json").read_text())
    pilot_names = set(snapshot["files"]) | {"SNAPSHOT_MANIFEST.json"}
    selected = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root):
            continue
        if any(x.startswith(".") or x == "__pycache__" or x.endswith(".egg-info") for x in rel.parts):
            continue
        allowed = len(rel.parts) == 1 and rel.name in TOP_FILES
        allowed |= rel.parts[0] in SOURCE_SUFFIXES and p.suffix in SOURCE_SUFFIXES[rel.parts[0]]
        allowed |= len(rel.parts) == 3 and rel.parts[:2] == ("data", "pilot") and rel.name in pilot_names
        if allowed:
            selected.append((p, rel.as_posix()))
    hashes = {rel: hashlib.sha256(p.read_bytes()).hexdigest() for p, rel in selected}
    guard = json.loads((root / "policy/guard_manifest.json").read_text())
    mismatches = [name for name, digest in guard["files"].items() if hashes.get(name) != digest]
    manifest = {
        "kind": "separately_identified_source_package",
        "files": hashes,
        "guard_state": "UNSEALED_REVIEW_REQUIRED" if mismatches else "MATCHES_MANIFEST",
        "guard_mismatches": mismatches,
        "excludes": "runs, caches, credentials, venvs, models",
    }
    with output.open("xb") as target:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for p, rel in selected:
                z.write(p, "universe-real-harness/" + rel)
            z.writestr("universe-real-harness/PACKAGE_MANIFEST.json", json.dumps(manifest, indent=2))
    return {
        "output": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "bytes": output.stat().st_size,
        "guard_state": manifest["guard_state"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(package(Path(__file__).resolve().parents[1], args.output), indent=2))
