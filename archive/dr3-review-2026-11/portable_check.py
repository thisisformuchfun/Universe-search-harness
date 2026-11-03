"""Offline check for the two public FITS products in the portable handoff."""
from pathlib import Path
import hashlib,importlib.util,json
import numpy as np
from astropy.io import fits

ROOT=Path(__file__).resolve().parent
HELPER=ROOT/'research/orientation/orientation_v1.py'
PRODUCTS=(('held',ROOT/'evidence/held_sedr5.fit','7a33d6a4ff8594c33b43181309bc5ad4e0739e6245943e06ba099172d04742de'),
          ('reference',ROOT/'evidence/reference_sedr5.fit','0e1c7ac03810cd41ad1df477f0977d82e92ba1bad71e442912ca282b339fb439'))

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''): h.update(block)
    return h.hexdigest()
def main():
    spec=importlib.util.spec_from_file_location('orientation',HELPER)
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    result=[]
    for label,path,expected in PRODUCTS:
        if sha(path)!=expected: raise ValueError('product checksum mismatch: '+label)
        with fits.open(path,memmap=False) as hdus:
            if len(hdus)<2 or type(hdus[1]).__name__!='BinTableHDU' or len(hdus[1].data)!=1:
                raise ValueError('unexpected FITS structure: '+label)
            data=hdus[1].data; fields={k:data[k][0] for k in helper.FIELDS}
            if any(np.ma.isMaskedArray(a) or a.shape!=(6,4136) for a in fields.values()):
                raise ValueError('unexpected pixel shape or mask: '+label)
            frames=[]
            for i in range(6):
                original={k:v[i] for k,v in fields.items()}
                ordered,reverse=helper.orient(original)
                if not all((ordered[k][::-1] if reverse else ordered[k]).tobytes()==original[k].tobytes()
                           and ordered[k].dtype==original[k].dtype for k in helper.FIELDS):
                    raise ValueError('roundtrip mismatch: '+label)
                frames.append('descending' if reverse else 'ascending')
        if sha(path)!=expected: raise ValueError('source changed during read: '+label)
        result.append({'product':label,'sha256':expected,'frame_orientations':frames,'byte_roundtrip':True})
    print(json.dumps({'status':'OFFLINE_INDEX_BOOKKEEPING_CHECKED','products':result,
                      'qualification':'no calibration, RV, source attribution or scientific claim'},indent=2))
if __name__=='__main__': main()
