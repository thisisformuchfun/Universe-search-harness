"""Verify every file listed in the GitHub export manifest without executing data."""
from pathlib import Path, PurePosixPath
import hashlib
import json

ROOT = Path(__file__).resolve().parent


def main():
    manifest = json.loads((ROOT / "EXPORT_MANIFEST.json").read_text(encoding="utf-8"))
    seen = set()
    for entry in manifest["files"]:
        name = entry["path"]
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts or ":" in name or name in seen:
            raise ValueError("Invalid or duplicate manifest path")
        seen.add(name)
        file_path = ROOT.joinpath(*path.parts)
        if not file_path.resolve().is_relative_to(ROOT.resolve()) or not file_path.is_file():
            raise ValueError(f"Missing or unsafe file: {name}")
        raw = file_path.read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Hash mismatch: {name}")
    print(f"Verified {len(seen)} export files. This checks integrity, not scientific truth or redistribution rights.")


if __name__ == "__main__":
    main()
