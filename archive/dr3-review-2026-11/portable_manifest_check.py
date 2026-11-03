"""Verify an extracted bundle against an externally supplied manifest SHA256."""
from pathlib import Path, PurePosixPath
import argparse,hashlib,json,os,re,stat
r=Path(__file__).resolve().parent
def require(condition,message):
 if not condition: raise ValueError(message)
p=argparse.ArgumentParser();p.add_argument('--expected-manifest-sha256',required=True);a=p.parse_args()
mp=r/'PORTABLE_MANIFEST.json';info=mp.lstat()
require(not stat.S_ISLNK(info.st_mode) and not (getattr(info,'st_file_attributes',0)&0x400),'manifest symlink/reparse')
raw=mp.read_bytes()
require(bool(re.fullmatch('[0-9a-f]{64}',a.expected_manifest_sha256)) and hashlib.sha256(raw).hexdigest()==a.expected_manifest_sha256,'manifest SHA mismatch')
m=json.loads(raw);seen=set()
for x in m['files']:
 name=x['member'];parts=PurePosixPath(name).parts
 require(bool(parts) and '..' not in parts and name not in seen,'unsafe or duplicate member')
 seen.add(name);p=r
 for part in parts:
  p=p/part;info=p.lstat();require(not stat.S_ISLNK(info.st_mode) and not (getattr(info,'st_file_attributes',0)&0x400),'member symlink/reparse')
 require(p.resolve().is_relative_to(r),'member escaped root');b=p.read_bytes()
 require(len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256'],'member hash mismatch: '+name)
actual=set()
for root,dirs,files in os.walk(r,followlinks=False):
 for name in dirs+files:
  path=Path(root)/name;info=path.lstat();require(not stat.S_ISLNK(info.st_mode) and not (getattr(info,'st_file_attributes',0)&0x400),'extra symlink/reparse')
 for name in files:actual.add((Path(root)/name).relative_to(r).as_posix())
require(actual==seen|{'PORTABLE_MANIFEST.json'},'extra or missing files')
require(hashlib.sha256((r/'baseline/original-v1.zip').read_bytes()).hexdigest()==m['original_baseline_sha256'],'baseline SHA mismatch')
print('verified',len(seen),'members, no extra files, and original baseline')
