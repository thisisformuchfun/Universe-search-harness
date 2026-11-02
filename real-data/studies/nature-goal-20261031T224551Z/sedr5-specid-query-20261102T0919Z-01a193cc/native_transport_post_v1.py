"""Two frozen SEDR5 public catalogue POSTs; reviewed terminal guards."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, subprocess, time
CURL = "C:/Windows/System32/curl.exe"
LIMITS = {"body_bytes":1000000,"header_bytes":65536,"stdout_bytes":4096,"stderr_bytes":262144,
          "curl_seconds":45,"process_seconds":48,"poll_seconds":0.02,"owned_process_cleanup_seconds":2}
URL = 'https://nadc.china-vo.org/data/data/general/sedr5/sexprv/build.csvs'
REQUEST_URLS = {'control': URL, 'target': URL}
PAYLOADS = {}
CONTENT_TYPE = 'Content-Type: multipart/form-data; boundary=astra-sedr5-01a193cc-boundary'

def utc(): return datetime.now(timezone.utc).isoformat()
def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()
def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())

def cleanup_owned(proc, rec):
    if proc is not None and proc.poll() is None:
        try:
            rec["owned_process_kill_issued"]=True
            proc.kill()
            proc.wait(timeout=LIMITS["owned_process_cleanup_seconds"])
        except Exception as exc:
            rec["cleanup_error_type"]=type(exc).__name__
    if proc is None:
        rec["cleanup_status"]="NOT_STARTED"
    elif proc.poll() is None:
        rec["cleanup_status"]="EXIT_UNCONFIRMED"
    else:
        rec["cleanup_status"]="EXIT_CONFIRMED"

def fetch(out, request, name, batch_deadline_ns, owner_callback=None):
    expected = PAYLOADS.get(name)
    if (REQUEST_URLS.get(name) != request.get("url") or request.get("method") != "POST"
            or expected is None or request.get("payload_sha256") != expected[1]
            or sha(expected[0]) != expected[1]):
        raise ValueError("Not a frozen public catalogue request")
    NAME=name
    raw=out/(NAME+".raw"); headers=out/(NAME+".headers"); stdout=out/(NAME+".curl.stdout"); stderr=out/(NAME+".curl.stderr")
    for path in (raw, headers, stdout, stderr, out/(NAME+".json"), out/(NAME+".request.json")):
        if path.exists(): raise FileExistsError(path)
    for path in (raw, headers):
        with path.open("xb"):
            pass
    begun=time.perf_counter_ns(); deadline=min(begun+LIMITS["process_seconds"]*1_000_000_000,batch_deadline_ns-LIMITS["owned_process_cleanup_seconds"]*1_000_000_000)
    curl_seconds=min(LIMITS["curl_seconds"],max(1,int((deadline-begun)/1e9)-3))
    command=[CURL,"--disable","--proto","=https","--connect-timeout","15","--max-time",str(curl_seconds),
             "--max-filesize",str(LIMITS["body_bytes"]),"--silent","--show-error","--dump-header",str(headers),
             "--output",str(raw),"--write-out","%{http_code}\n%{ssl_verify_result}\n%{size_download}\n%{num_redirects}\n%{url_effective}\n",
             "--header",CONTENT_TYPE,"--data-binary",'@'+str(expected[0]),"--url",request["url"]]
    save(out/(NAME+".request.json"),{"started_utc":utc(),"request":request,"command":command,"limits":LIMITS,"batch_deadline_ns":batch_deadline_ns,"effective_curl_seconds":curl_seconds})
    rec={"status":"FAILED_VISIBLE","started_utc":utc(),"query":None,"url":request["url"],
         "request_sha256":sha(out/(NAME+".request.json")),"returncode":None,"http_status":None,
         "limit_failure":None,"owned_process_kill_issued":False,"owned_pid":None,"cleanup_status":"NOT_STARTED","polling_overshoot_possible":True}
    proc=None
    try:
        with stdout.open("xb") as so, stderr.open("xb") as se:
            if deadline-time.perf_counter_ns()<4_000_000_000:raise TimeoutError("Insufficient remaining batch time before process creation")
            proc=subprocess.Popen(command,stdout=so,stderr=se,shell=False)
            rec["owned_pid"]=proc.pid
            if owner_callback is not None:
                owner_callback(proc)
            while True:
                sizes={p.name:p.stat().st_size if p.exists() else 0 for p in (raw,headers,stdout,stderr)}
                if sizes[raw.name]>LIMITS["body_bytes"]:rec["limit_failure"]="BODY_CAP"
                elif sizes[headers.name]>LIMITS["header_bytes"]:rec["limit_failure"]="HEADER_CAP"
                elif sizes[stdout.name]>LIMITS["stdout_bytes"] or sizes[stderr.name]>LIMITS["stderr_bytes"]:rec["limit_failure"]="DIAGNOSTIC_CAP"
                elif time.perf_counter_ns()>=deadline:rec["limit_failure"]="PROCESS_DEADLINE"
                code=proc.poll()
                if rec["limit_failure"]:
                    if code is None:rec["owned_process_kill_issued"]=True;proc.kill()
                    # The finally block owns the sole bounded cleanup wait.
                    raise RuntimeError(rec["limit_failure"])
                if code is not None:break
                time.sleep(LIMITS["poll_seconds"])
            rec["returncode"]=proc.returncode
        # The last poll can observe exit after final writes; sample again after exit
        # and after closing our handles, before reading native JSON or response data.
        terminal_sizes={p.name:p.stat().st_size if p.exists() else 0 for p in (raw,headers,stdout,stderr)}
        terminal_ns=time.perf_counter_ns()
        rec.update(terminal_sizes=terminal_sizes,terminal_elapsed_perf_counter_seconds=(terminal_ns-begun)/1e9)
        if terminal_sizes[raw.name]>LIMITS["body_bytes"]:rec["limit_failure"]="BODY_CAP"
        elif terminal_sizes[headers.name]>LIMITS["header_bytes"]:rec["limit_failure"]="HEADER_CAP"
        elif terminal_sizes[stdout.name]>LIMITS["stdout_bytes"] or terminal_sizes[stderr.name]>LIMITS["stderr_bytes"]:rec["limit_failure"]="DIAGNOSTIC_CAP"
        elif terminal_ns>=deadline:rec["limit_failure"]="PROCESS_DEADLINE"
        if rec["limit_failure"]:raise RuntimeError(rec["limit_failure"])
        lines=stdout.read_text(encoding="utf-8",errors="strict").splitlines()
        if len(lines)!=5 or not all(v.isdigit() for v in lines[:4]):raise ValueError("Malformed bounded native status")
        info=dict(zip(("http_code","ssl_verify_result","size_download","num_redirects"),map(int,lines[:4])))
        info["url_effective"]=lines[4]
        rec.update(http_status=info.get("http_code"),ssl_verify_result=info.get("ssl_verify_result"),
                   num_redirects=info.get("num_redirects"),effective_url=info.get("url_effective"),reported_body_bytes=info.get("size_download"))
        if any(type(rec[k]) is not int for k in ("http_status","ssl_verify_result","num_redirects","reported_body_bytes")):
            raise ValueError("Missing/noninteger native transfer status")
        if rec["returncode"]!=0 or rec["http_status"]!=200 or rec["ssl_verify_result"]!=0 or rec["num_redirects"]!=0 or rec["effective_url"]!=request["url"]:
            raise ValueError("HTTP/TLS/curl/redirect/effective-URL failure")
        if not raw.exists() or raw.stat().st_size!=rec["reported_body_bytes"]:raise ValueError("Missing/truncated response")
        rec["status"]="HTTP_COMPLETE_UNPARSED"
    except Exception as exc:rec.update(error_type=type(exc).__name__,error=str(exc)[:300])
    finally:
        cleanup_owned(proc, rec)
        rec.update(finished_utc=utc(),elapsed_perf_counter_seconds=(time.perf_counter_ns()-begun)/1e9,
                   returncode=proc.returncode if proc is not None else None)
        if rec["cleanup_status"] == "EXIT_UNCONFIRMED":
            rec["native_file_hashes"]="DEFERRED_UNTIL_EXIT_CONFIRMED"
            rec["body_overage_bytes"]=None
            rec["header_overage_bytes"]=None
            rec["native_stdout_overage_bytes"]=None
            rec["native_stderr_overage_bytes"]=None
        else:
            for path in (raw,headers,stdout,stderr):
                key={raw:"raw",headers:"headers",stdout:"native_stdout",stderr:"native_stderr"}[path]
                rec[key+"_present"]=path.exists()
                if path.exists():rec[key+"_bytes"]=path.stat().st_size;rec[key+"_sha256"]=sha(path)
            rec["body_overage_bytes"]=max(0,rec.get("raw_bytes",0)-LIMITS["body_bytes"])
            rec["header_overage_bytes"]=max(0,rec.get("headers_bytes",0)-LIMITS["header_bytes"])
            rec["native_stdout_overage_bytes"]=max(0,rec.get("native_stdout_bytes",0)-LIMITS["stdout_bytes"])
            rec["native_stderr_overage_bytes"]=max(0,rec.get("native_stderr_bytes",0)-LIMITS["stderr_bytes"])
        save(out/(NAME+".json"),rec)
    return rec
