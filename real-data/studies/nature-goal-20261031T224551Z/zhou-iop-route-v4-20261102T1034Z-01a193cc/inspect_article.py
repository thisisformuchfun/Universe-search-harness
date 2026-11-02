"""Offline inert article-page inspection; never follows a page link."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import hashlib, json, os, re

D = Path(__file__).resolve().parent
URL = 'https://iopscience.iop.org/article/10.3847/1538-4357/aeaa3a'
BODY_SHA = '88beb44cd30930f0f48dbb6746a2abe040d6f014ce26cc0aae7f069cef221ae6'
RESULT_SHA = '1eb1a15f66b33c25b3061255ac77ed6b9254e669fd54d90058d372c4567a3da4'
SAMPLE_IDS = ('3443894276188890752', '1560560462739675904', '1893474166810285952',
              '470096784872760192', '3369415484530173696', '2876854139510029184')

class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = None
        self.links = []
        self.meta = []
        self.meta_ambiguous = False
    def handle_starttag(self, tag, attrs):
        keys = [str(key).lower() for key,_ in attrs]
        duplicate = len(keys) != len(set(keys))
        if tag.lower() == 'meta' and duplicate:
            self.meta_ambiguous = True
            return
        if tag.lower() == 'a' and duplicate:
            self.active = None
            return
        data = dict(attrs)
        if tag.lower() == 'meta' and str(data.get('name','')).lower() in ('citation_doi','citation_title'):
            self.meta.append((str(data.get('name','')).lower(), data.get('content','')))
        if tag.lower() == 'a':
            if self.active is not None: self.active = None
            self.active = [data.get('href',''), []]
    def handle_data(self, data):
        if self.active is not None: self.active[1].append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self.active is not None:
            self.links.append((self.active[0], ' '.join(self.active[1]).strip()))
            self.active = None

def digest(b): return hashlib.sha256(b).hexdigest()
def inspect(body):
    if len(body) > 2000000 or b'\x00' in body: raise ValueError('unsupported HTML bytes')
    text = body.decode('utf-8', errors='strict')
    parser = Links(); parser.feed(text); parser.close()
    entries = []
    for href, label in parser.links:
        if not isinstance(href,str) or not re.search(r'machine.readable|\bmrt\b|download table', label, re.I):
            continue
        try:
            parts = urlsplit(urljoin(URL, href))
            host = parts.hostname if parts.hostname in ('iopscience.iop.org','content.cld.iop.org') else 'OTHER'
        except (ValueError, UnicodeError):
            continue
        entries.append({'label_category':'machine-readable', 'scheme':parts.scheme if parts.scheme in ('http','https') else 'OTHER',
                        'host_category':host, 'path_sha256':digest(parts.path.encode('utf-8')),
                        'query_present':bool(parts.query), 'fragment_present':bool(parts.fragment),
                        'userinfo_present':parts.username is not None or parts.password is not None})
    if len(entries) > 25: raise ValueError('too many candidate links')
    dois = {value.lower() for key,value in parser.meta if key == 'citation_doi' and isinstance(value,str)}
    titles = {re.sub(r'\s+',' ',value.lower()) for key,value in parser.meta if key == 'citation_title' and isinstance(value,str)}
    doi_ok = not parser.meta_ambiguous and dois == {'10.3847/1538-4357/aeaa3a'}
    title_ok = (not parser.meta_ambiguous and len(titles) == 1 and 'a sample of long-period binaries with dormant compact-object candidates' in next(iter(titles)))
    challenge = bool(re.search(r'captcha|verify you are human|cloudflare.{0,30}challenge', text, re.I))
    if not doi_ok or not title_ok or challenge:
        entries = []
    return {'body_sha256':digest(body), 'body_bytes':len(body),
            'citation_doi_exact':doi_ok, 'citation_title_contains_expected':title_ok,
            'lexical_id_occurrences_not_table_validation':{key:len(re.findall(r'(?<![0-9])'+re.escape(key)+r'(?![0-9])',text)) for key in SAMPLE_IDS},
            'table_controls_verified':False,
            'candidate_table_links':entries,
            'challenge_marker_present':challenge,
            'challenge_marker_absence_is_not_clearance':True,
            'scope':'inert page inspection; untrusted labels and paths withheld; no link followed'}

def main():
    body = (D/'capture-v9'/'article.raw').read_bytes()
    result = (D/'capture-v9'/'RESULTS.json').read_bytes()
    if digest(body) != BODY_SHA or digest(result) != RESULT_SHA: raise ValueError('capture evidence changed')
    transport = json.loads(result)
    if transport.get('status') != 'STOP_UNPARSED_CONTENT' or transport.get('owned_process_exit_confirmed') is not True:
        raise ValueError('unexpected transport state')
    obj = inspect(body)
    encoded = (json.dumps(obj, indent=2)+'\n').encode()
    with (D/'ARTICLE_INSPECTION.json').open('xb') as f:
        f.write(encoded); f.flush(); os.fsync(f.fileno())
    print(json.dumps(obj))

if __name__ == '__main__': main()
