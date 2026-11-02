"""Production CLI: real Gaia data only; autonomous ranking is not discovery proof."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,platform,sys,time
from pathlib import Path
from collections import Counter
from harness2.core.guards import ROOT,verify_guard,disposition,sha
from harness2.core.library import ContinualLibrary,atomic_json
from harness2.core.recursion import Harness2Engine,partition,utility
from harness2.core.components import HarnessBundle
from harness2.providers.router import LLMConfig,UniversalModelRouter
from harness2.universe.detectors.signal_pipeline import measure,identity
from harness2.universe.connectors.public_archives import PublicSkyConnector,load_csv_snapshot,ArchiveError,utc_now
from harness2.universe.novelty import bundled_catalogs,augment_live


def snapshot():
    manifest=json.loads((ROOT/'data/pilot/SNAPSHOT_MANIFEST.json').read_text())
    for name,digest in manifest['files'].items():
        if sha(ROOT/'data/pilot'/name)!=digest: raise ValueError('Bundled snapshot changed: '+name)
    original=json.loads((ROOT/'data/pilot/provenance.json').read_text())
    rows=load_csv_snapshot(ROOT/'data/pilot/gaia_pilot_raw.csv',original['raw_sha256'])
    return rows,{'mode':'OFFLINE_REAL_SNAPSHOT_NOT_FRESH','original_provenance':original,'rows':len(rows)}

def summarize(records):
    counts=dict(Counter(r['status'] for r in records));anomalies=[r for r in records if r['f_phot_solar']>3]
    return {'records':len(records),'distinct_sources':len(set(r['source_id'] for r in records)),
      'observable_above3':len(anomalies),'anomaly_status_counts':dict(Counter(r['status'] for r in anomalies)),
      'all_status_counts':counts,'new_candidates':[],'releasable_novel_candidates':0,
      'label':'Photocentre-orbit anomaly review queue. Not companion masses or black-hole detections.'}

def evaluate_holdout(run_dir,ledger):
    guard=verify_guard();run_dir=Path(run_dir)
    frozen=json.loads((run_dir/'run_manifest.json').read_text())
    for name,digest in frozen['output_hashes'].items():
        if Path(name).name!=name or sha(run_dir/name)!=digest: raise ValueError('Run output changed before held-out evaluation')
    if frozen['guard_hash']!=guard: raise ValueError('Policy changed since run')
    ledger=Path(ledger); entries=json.loads(ledger.read_text()) if ledger.exists() else {}
    dataset=frozen['dataset_sha256']
    if dataset in entries: raise ValueError('This dataset holdout has already been evaluated. Do not retune against it; acquire/pre-register a new independent holdout.')
    records=json.loads((run_dir/'records.json').read_text())
    test=[r for r in records if r['status']=='HOLD_QUALITY_AND_NOVELTY' and partition(r['source_id'])=='test']
    consumed={sid for entry in entries.values() for sid in entry.get('test_source_ids',[])}
    if consumed.intersection(r['source_id'] for r in test): raise ValueError('Overlapping test source IDs already consumed by earlier holdout evaluation')
    engine=json.loads((run_dir/'recursion.json').read_text());cfg=HarnessBundle.from_dict(engine['adopted_configuration'])
    result={'dataset_sha256':dataset,'guard_hash':guard,'evaluated_at_utc':utc_now(),
      'configuration':cfg.to_dict(),'heldout_utility':utility(test,cfg,engine['review_budget']), 'review_budget':engine['review_budget'], 'test_source_ids':sorted(set(r['source_id'] for r in test)),
      'meaning':'One frozen ranking-utility evaluation, not astrophysical validation. Do not feed this result into adaptive prompts.'}
    entries[dataset]=result;atomic_json(ledger,entries);atomic_json(run_dir/'heldout_evaluation.json',result)
    return result

def run(args):
    guard=verify_guard(); out=Path(args.output)
    if (out/'run_manifest.json').exists(): raise ValueError('Completed output exists; choose a new run directory')
    out.mkdir(parents=True,exist_ok=True)
    connector=PublicSkyConnector(args.cache,timeout=args.timeout,retries=args.retries)
    known,coverage=bundled_catalogs()
    if args.live:
        schema=connector.gaia_schema()
        acquisition=connector.gaia_nss_pages(out/'acquisition',args.page_size,args.max_pages,args.resume)
        rows,provenance=acquisition.rows,acquisition.provenance
        # Failure stops the run; no implicit stale-catalog substitution in live mode.
        coverage+=augment_live(known,connector.vizier_known_catalogs())
        provenance={'mode':'LIVE_REAL_ARCHIVE','acquisition':provenance,
                    'source_schema':schema.provenance}
    else: rows,provenance=snapshot()
    if not rows: raise ValueError('No real source rows received; no empty success run')
    keys=[identity(r) for r in rows]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate source/solution records')
    dataset_hash=hashlib.sha256(json.dumps(sorted(rows,key=identity),sort_keys=True,allow_nan=False).encode()).hexdigest()
    records=[];invalid=[]
    for row in rows:
        try:
            r=measure(row,args.draws,args.backend);r.update(disposition(r,known));r['partition']=partition(r['source_id'])
            records.append(r)
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            invalid.append({'record_id':identity(row),'error':str(exc)})
    if not records: raise ValueError('All rows invalid; analysis aborted')
    # API enrichments are evidence only: missing matches never clear novelty.
    context={'status':'NOT_REQUESTED'}
    if args.context:
        ids=list(dict.fromkeys(r['source_id'] for r in records if r['status']=='HOLD_QUALITY_AND_NOVELTY'))[:100]
        if ids:
            context={'gaia':connector.gaia_context(ids).to_dict(),'simbad':connector.simbad_exact_ids(ids).to_dict(),
              'limit':'At most100 held sources. SIMBAD identification is not literature clearance or BH status.'}
    router=UniversalModelRouter(LLMConfig.from_env(args.provider,args.model))
    engine=Harness2Engine(router,ContinualLibrary(args.memory))
    recursion,ranked=engine.run_task(records,args.k,args.mode,args.review_budget)
    if verify_guard()!=guard:raise RuntimeError('Guard changed during execution')
    for r in ranked:
        r['review_links']={
          'gaia_source':'https://gea.esac.esa.int/archive/',
          'simbad':'https://simbad.cds.unistra.fr/simbad/sim-id?Ident=Gaia+DR3+'+r['source_id'],
          'ads_search':'https://ui.adsabs.harvard.edu/search/q='+r['source_id'],
          'warning':'Links are for human follow-up, not proof of absence in literature.'}
    payloads={'records.json':records,'raw_rows.json':rows,'review_queue.json':ranked,'recursion.json':recursion,
      'provenance.json':provenance,'catalog_coverage.json':coverage,'context.json':context,'invalid_rows.json':invalid,
      'summary.json':dict(summarize(records),invalid_rows=len(invalid),data_mode=provenance['mode'])}
    for name,payload in payloads.items():atomic_json(out/name,payload)
    fields=['source_id','nss_solution_type','f_phot_solar','a0_mas','status','novelty_status','partition']
    with (out/'review_queue.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fields,extrasaction='ignore');w.writeheader();w.writerows(ranked)
    review={'instructions':'Fill with source-linked independent evidence. This file does not override automatic holds.',
      'fields':['source_id','orbit_validation_evidence','full_covariance_review','luminous_blend_triple_tests','current_literature_search_date','literature_queries','reviewer','decision'],
      'release_enabled':False}
    atomic_json(out/'human_review_template.json',review)
    hashes={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    manifest={'created_at_utc':utc_now(),'version':'1.0.0-real','python':sys.version,'platform':platform.platform(),
      'guard_hash':guard,'dataset_sha256':dataset_hash,'output_hashes':hashes,'live':bool(args.live),
      'gpu_requested':args.backend=='cuda','gpu_benchmark_claim':False,
      'unsupported_production_domains':['exoplanet_transit','gw_subthreshold_merger','anomalous_star']}
    atomic_json(out/'run_manifest.json',manifest)
    return payloads['summary.json']

def parser():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('run',help='Real measured Gaia NSS pipeline; snapshot default, --live explicit')
    r.add_argument('--live',action='store_true');r.add_argument('--output',required=True)
    r.add_argument('--cache',default='data/cache');r.add_argument('--memory',default='runs/memory.json')
    r.add_argument('--k',type=int,default=2);r.add_argument('--mode',choices=['parallel','sequential'],default='parallel')
    r.add_argument('--provider',choices=['deterministic','local'],default='deterministic');r.add_argument('--model',default=None)
    r.add_argument('--draws',type=int,default=4096);r.add_argument('--backend',choices=['numpy','cuda'],default='numpy')
    r.add_argument('--review-budget',type=int,default=20);r.add_argument('--page-size',type=int,default=500)
    r.add_argument('--max-pages',type=int,default=2);r.add_argument('--resume',action='store_true');r.add_argument('--context',action='store_true')
    r.add_argument('--timeout',type=int,default=30);r.add_argument('--retries',type=int,default=2)
    h=sub.add_parser('evaluate-holdout');h.add_argument('--run',required=True);h.add_argument('--ledger',default='runs/heldout-ledger.json')
    s=sub.add_parser('probe');s.add_argument('--output',default='runs/connectivity.json');s.add_argument('--cache',default='data/cache');s.add_argument('--timeout',type=int,default=15);s.add_argument('--retries',type=int,default=0)
    sub.add_parser('verify',help='Verify scientific code hashes and bundled real data')
    return p

def main():
    args=parser().parse_args()
    try:
        if args.command=='verify': result={'guard':verify_guard(),'snapshot_rows':len(snapshot()[0]),'known_catalogs':bundled_catalogs()[1]}
        elif args.command=='run': result=run(args)
        elif args.command=='evaluate-holdout':result=evaluate_holdout(args.run,args.ledger)
        else:
            result=PublicSkyConnector(args.cache,args.timeout,args.retries).probe();atomic_json(args.output,result)
            print(json.dumps(result,indent=2));return 0 if result['all_passed'] else 2
        print(json.dumps(result,indent=2));return 0
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        print('FAILED CLOSED: '+str(exc),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
