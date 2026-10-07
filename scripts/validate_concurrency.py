#!/usr/bin/env python3
"""Ensayo real opcional: dos slices pequeños concurrentes y protección de la base compartida."""
import argparse
import concurrent.futures
import json
import os
import sys
import time
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from g5.cli import request
from g5.demo import save,wait
from g5.model import require
from g5.backend import SSHBackend


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image',required=True,help='JSON de importación CirrOS')
    p.add_argument('--run',required=True)
    p.add_argument('--config',default='config/cluster.json')
    p.add_argument('--token-file',default='config/admin.token')
    a=p.parse_args();out=Path(a.run)
    require(not out.exists(),'Use una carpeta --run nueva; las anteriores conservan evidencia')
    out.mkdir(parents=True)
    cfg=json.loads(Path(a.config).read_text());token=Path(a.token_file).read_text().strip()
    image=json.loads(Path(a.image).read_text())['id'];backend=SSHBackend(cfg)
    jobs=[];report={'status':'RUNNING','checks':[]}
    def call(method,path,body=None,key=None):return request('http://127.0.0.1:8085',token,method,path,body,key)
    def check(name,ok,evidence=None):
        report['checks'].append({'name':name,'pass':bool(ok),'evidence':evidence});save(out/'resultado.json',report)
        require(ok,'Falló '+name);print('PASS '+name,flush=True)
    try:
        check('backend-real',not call('GET','/v1/capabilities')['simulated'])
        require(not any(r['reserved'] for r in call('GET','/v1/slices')),'Ejecute sin otros slices activos')
        requests=[]
        for k in range(2):
            spec={'name':'concurrencia-'+str(k),'networks':[{'name':'link','cidr':'192.168.90.0/27','cvid':190,'dhcp':False}],
                  'vms':[{'name':'vm'+str(n),'worker':'server'+str(n),'image':image,'vcpus':1,'memory_mb':512,'disk_gb':1,'guest':{'os':'cirros'},'internet':False,'nics':[{'name':'link0','network':'link','ip':'192.168.90.'+str(10+n)}]} for n in (1,2)],'publications':[]}
            item={'key':uuid.uuid4().hex,'spec':spec};requests.append(item)
        save(out/'requests.json',requests)
        def create(item):
            job=call('POST','/v1/slices',item['spec'],item['key'])
            save(out/(item['spec']['name']+'-job.json'),job)
            return job
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(create,item) for item in requests]
            errors=[]
            for future in futures:
                try:jobs.append(future.result())
                except Exception as exc:errors.append(str(exc))
            require(not errors,'; '.join(errors))
            waits=[pool.submit(wait,call,j) for j in jobs]
            for f in waits:f.result()
        rows=[call('GET','/v1/slices/'+j['slice_id']) for j in jobs];save(out/'slices.json',rows)
        check('dos-slices-ready',all(r['status']=='READY' for r in rows))
        check('cvid-reutilizada-svid-distinta',len({r['plan']['svid'] for r in rows})==2 and len({r['plan']['networks'][0]['cvid'] for r in rows})==1)
        for item,job in zip(requests,jobs):
            check('idempotencia-'+item['spec']['name'],call('POST','/v1/slices',item['spec'],item['key'])['id']==job['id'])
        wait(call,call('DELETE','/v1/slices/'+jobs[0]['slice_id'],key=uuid.uuid4().hex))
        d=call('GET','/v1/slices/'+jobs[1]['slice_id']+'/diagnostics');save(out/'survivor.json',d)
        check('otro-slice-sigue-activo',all(n['ok'] for n in d['nodes'].values()))
        for node in ('server1','server2'):
            gc=call('POST','/v1/nodes/'+node+'/cache/gc',{'all_unused':True})
            check('base-compartida-conservada-'+node,image in gc['pinned'] and image not in gc['removed'],gc)
        report['status']='PASS'
    except Exception as exc:
        report['status']='FAILED';report['error']=str(exc)
    finally:
        for j in jobs:
            try:
                if call('GET','/v1/slices/'+j['slice_id'])['status']!='DELETED':
                    wait(call,call('DELETE','/v1/slices/'+j['slice_id'],key=uuid.uuid4().hex))
            except Exception as exc:
                report.setdefault('cleanup_errors',[]).append(str(exc));report['status']='FAILED'
        try:save(out/'final-inventory.json',{n:backend.call(n,'inventory') for n in ('server1','server2')})
        except Exception as exc:report['inventory_error']=str(exc);report['status']='FAILED'
        save(out/'resultado.json',report);print(json.dumps(report,indent=2))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
