"""Retrieve only the official SEDR5 sample CSV, with bounded local evidence."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid

D = Path(__file__).resolve().parent
T = D.parent
S = D.parents[2]
C = S.parent / "coordination"
LOCK = C / "sedr5-acquisition.lock"
PRIOR = T / "held1533-sedr5-20261102T081926Z-01a193cc"
LIB = PRIOR / "capture_serial_v9.py"
TRANSPORT = PRIOR / "native_transport_sedr5_v5.py"
PROTOCOL = D / "PROTOCOL.md"
MANIFEST = D / "MANIFEST.json"
URL = "https://dr5.lamost.org/sedr5/sexprv-sample.csv"
BODY_CAP = 262144


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def sample_schema(raw):
    if not raw or len(raw) > BODY_CAP or b"\x00" in raw:
        raise ValueError("unsupported sample size or bytes")
    rows = csv.reader(io.StringIO(raw.decode("utf-8-sig", errors="strict"), newline=""), strict=True)
    header = next(rows, None)
    if not header or len(header) > 100 or len(set(header)) != len(header):
        raise ValueError("invalid sample header")
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) for name in header):
        raise ValueError("unexpected sample field name")
    if not {"specid", "iexp", "mjm", "rv", "rverr", "filename"}.issubset(header):
        raise ValueError("required sample fields absent")
    count = 0
    for row in rows:
        if len(row) != len(header):
            raise ValueError("sample row width mismatch")
        count += 1
        if count > 10000:
            raise ValueError("sample row bound exceeded")
    return {"fields": header, "data_rows": count}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(expected):
    if not re.fullmatch("[0-9a-f]{64}", expected) or sha(MANIFEST) != expected:
        raise ValueError("manifest mismatch")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths = {"script_sha256": Path(__file__), "protocol_sha256": PROTOCOL,
             "library_sha256": LIB, "transport_sha256": TRANSPORT,
             "test_sha256": D / "test_sample.py", "test_result_sha256": D / "TEST_RESULT.json"}
    if any(sha(path) != manifest[key] for key, path in paths.items()):
        raise ValueError("pinned input mismatch")
    if manifest["library_sha256"] != "3f9b82d0ce290efc280dd4e70e1963045bc95aa527cf880387e6f8ccbcb525f5":
        raise ValueError("unexpected capture library")
    if manifest["transport_sha256"] != "0f6c1d71336306b5e0bb319f5ced7cfe0e059af891d6632d28f49e634c2c8f42":
        raise ValueError("unexpected transport")
    result = json.loads((D / "TEST_RESULT.json").read_text(encoding="utf-8"))
    if (result.get("returncode") != 0 or result.get("tests_expected") != 5
            or sha(D / "TEST_STDOUT.raw") != result.get("stdout_sha256")
            or sha(D / "TEST_STDERR.raw") != result.get("stderr_sha256")):
        raise ValueError("offline test evidence mismatch")
    version = subprocess.run(["C:/Windows/System32/curl.exe", "--disable", "--version"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=True).stdout.decode("ascii").splitlines()[0]
    match = re.match(r"^curl (\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (8, 4, 0):
        raise ValueError("curl body cap unavailable")
    return manifest, version


def main(expected):
    manifest, version = validate(expected)
    out = D / "capture-v1"
    out.mkdir(exist_ok=False)
    save(out / "CLAIM.json", {"started_utc": datetime.now(timezone.utc).isoformat(),
                              "manifest_sha256": expected, "curl_version": version})
    token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    lease = {"session": "astra-20261031T2113Z-01a193cc", "owner_token": token,
             "directory": str(D), "purpose": "SEDR5 sample preflight", "adapter_pid": os.getpid(),
             "acquired_utc": now.isoformat(), "expires_utc": (now + timedelta(minutes=3)).isoformat()}
    try:
        save(LOCK, lease)
    except FileExistsError:
        save(out / "RESULTS.json", {"status": "STOP_EXISTING_LEASE", "requests_started": 0})
        return 1
    owner = {"pid": None, "identity": None}
    cleanup_confirmed = True
    status = "STOP_NOT_STARTED"
    summary = {}
    interrupted = None
    try:
        lib = load_module("reviewed_capture_helpers", LIB)
        tr = load_module("reviewed_sample_transport", TRANSPORT)
        tr.REQUEST_URLS = {"sample": URL}
        tr.LIMITS.update(body_bytes=BODY_CAP, header_bytes=65536, stdout_bytes=4096, stderr_bytes=262144,
                         curl_seconds=30, process_seconds=33, poll_seconds=0.02,
                         owned_process_cleanup_seconds=2)
        deadline = time.perf_counter_ns() + 40_000_000_000
        request = {"name": "sample", "method": "GET", "url": URL, "manifest_sha256": expected,
                   "protocol_sha256": manifest["protocol_sha256"], "scope": "public sample schema only"}
        def on_spawn(proc):
            lib.bind_owned_pid(LOCK, token, out, "sample", proc, owner)
        cleanup_confirmed = False
        record = tr.fetch(out, request, "sample", deadline, owner_callback=on_spawn)
        cleanup_confirmed = record.get("cleanup_status") in ("NOT_STARTED", "EXIT_CONFIRMED")
        if not cleanup_confirmed:
            status = "STOP_OWNED_PROCESS_EXIT_UNCONFIRMED"
        else:
            raw, headers = out / "sample.raw", out / "sample.headers"
            valid = (record.get("status") == "HTTP_COMPLETE_UNPARSED" and record.get("http_status") == 200
                     and record.get("ssl_verify_result") == 0 and record.get("num_redirects") == 0
                     and record.get("effective_url") == URL and record.get("returncode") == 0
                     and raw.is_file() and raw.stat().st_size <= BODY_CAP and headers.is_file()
                     and headers.stat().st_size <= 65536 and sha(raw) == record.get("raw_sha256")
                     and sha(headers) == record.get("headers_sha256"))
            if not valid or not lib.valid_http_headers(headers.read_bytes(), 200, raw.stat().st_size):
                status = "STOP_TRANSPORT_OR_HEADERS"
            else:
                summary = sample_schema(raw.read_bytes())
                status = "SAMPLE_SCHEMA_DESCRIBED"
    except BaseException as exc:
        status = "STOP_EXCEPTION"
        summary = {"error_type": type(exc).__name__}
        interrupted = exc
    finally:
        current = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
        if current.get("owner_token") == token and cleanup_confirmed:
            LOCK.unlink()
        elif current.get("owner_token") == token:
            current.update({"cleanup_status": "EXIT_UNCONFIRMED", "last_owned_pid": owner["pid"],
                            "last_owned_process": owner["identity"],
                            "instruction": "Do not overwrite lease or kill by PID alone."})
            tmp = LOCK.with_name(LOCK.name + "." + token + ".tmp")
            save(tmp, current)
            if json.loads(LOCK.read_text(encoding="utf-8")).get("owner_token") != token:
                raise RuntimeError("lease owner changed")
            os.replace(tmp, LOCK)
        result = {"finished_utc": datetime.now(timezone.utc).isoformat(), "status": status,
                  "manifest_sha256": expected, "schema": summary,
                  "request_record_state": lib.read_json_state(out / "sample.request.json")[0] if "lib" in locals() else "UNKNOWN",
                  "owned_process_exit_confirmed": cleanup_confirmed, "last_owned_pid": owner["pid"],
                  "last_owned_process": owner["identity"], "lease_released": not LOCK.exists(),
                  "target_query_performed": False, "holdout_evaluated": False,
                  "native_headers_and_diagnostics": "local only; privacy review required before packaging"}
        save(out / "RESULTS.json", result)
    print(json.dumps({"status": status, "lease_released": result["lease_released"],
                      "schema": summary if status == "SAMPLE_SCHEMA_DESCRIBED" else None}), flush=True)
    if interrupted is not None and not isinstance(interrupted, Exception):
        raise interrupted
    return 0 if status == "SAMPLE_SCHEMA_DESCRIBED" else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: sample_fetch.py MANIFEST_SHA256")
    raise SystemExit(main(sys.argv[1]))
