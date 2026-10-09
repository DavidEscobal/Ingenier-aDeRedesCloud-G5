#!/usr/bin/env python3
"""Pruebas reales de EX1. No crea ni borra slices. No reemplaza la demostración VNC/SSH desde la notebook."""
import argparse
import base64
import concurrent.futures
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from g5.backend import SSHBackend
from g5.cli import request
from g5.demo import save


def rfb(token):
    try:
        with socket.create_connection(('127.0.0.1',6080),timeout=8) as s:
            key=base64.b64encode(os.urandom(16)).decode()
            s.sendall(('GET /websockify?token=%s HTTP/1.1\r\nHost: localhost:6080\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: %s\r\nSec-WebSocket-Protocol: binary\r\n\r\n'%(token,key)).encode())
            f=s.makefile('rb'); status=f.readline()
            while f.readline() not in (b'\r\n',b''):
                pass
            if b'101' not in status: return False
            h=f.read(2)
            if len(h)!=2 or h[0]&15!=2: return False
            n=h[1]&127
            if n==126: n=int.from_bytes(f.read(2),'big')
            elif n==127: n=int.from_bytes(f.read(8),'big')
            return n<=65536 and f.read(n).startswith(b'RFB ')
    except (OSError,ValueError):
        return False


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True)
    p.add_argument('--config',default='config/cluster.json')
    p.add_argument('--token-file',default='config/admin.token')
    p.add_argument('--url',default='http://127.0.0.1:8085')
    p.add_argument('--guest-key',default='~/.ssh/id_ed25519_ex1',help='Privada correspondiente a una pública incluida con demo build')
    a=p.parse_args()
    run=Path(a.run); out=run/('validation-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));out.mkdir(parents=True)
    cfg=json.loads(Path(a.config).read_text()); token=Path(a.token_file).read_text().strip()
    key=Path(a.guest_key).expanduser().resolve()
    backend=SSHBackend(cfg)
    report={'status':'RUNNING','checks':[],'manual_pending':['VPN del examen','Consolas VNC desde notebook: VM1, VM3, VM4 y VM5','SSH desde notebook a VM1 y VM3','Borrado final e inspección de workers']}
    def record(name,ok,evidence=None):
        report['checks'].append({'name':name,'pass':bool(ok),'evidence':evidence})
        save(out/'resultado.json',report)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not ok: raise RuntimeError('Falló '+name)
    def call(method,path,body=None):
        return request(a.url,token,method,path,body)
    try:
        record('backend-real',not call('GET','/v1/capabilities')['simulated'])
        record('gateway-local',socket.gethostname().split('.')[0].lower()==cfg['gateway']['name'].lower())
        sid=json.loads((run/'deployment.json').read_text())['job']['slice_id']
        row=call('GET','/v1/slices/'+sid); plan=row['plan']; save(out/'slice.json',row)
        record('slice-ready',row['status']=='READY')
        vms={v['name']:v for v in plan['vms']}
        expected={'vm1':'server1','vm2':'server2','vm3':'server3','vm4':'server1','vm5':'server2','vm6':'server3'}
        record('round-robin-ex1',{n:v['worker'] for n,v in vms.items()}==expected)
        edges={frozenset(v['name'] for v in plan['vms'] if any(n['network']==net['name'] for n in v['nics'])) for net in plan['networks'] if net['name'].startswith('link')}
        record('seis-enlaces-ex1',edges=={frozenset(x) for x in [('vm1','vm2'),('vm2','vm3'),('vm1','vm4'),('vm3','vm4'),('vm4','vm5'),('vm5','vm6')]})
        diag=call('GET','/v1/slices/'+sid+'/diagnostics');save(out/'diagnostics.json',diag)
        for vm in plan['vms']:
            real=diag['nodes'][vm['worker']]['vms'][vm['name']]
            record('pid-'+vm['name'],real['running'] and type(real['pid']) is int,real)
            command='ps -p %s -o pid=,args=; qemu-img info --force-share --output=json %s'%(real['pid'],shlex.quote(real['disk_path']))
            proc=subprocess.run(backend.ssh(vm['worker'])+['sudo -n sh -c '+shlex.quote(command)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=30)
            (out/(vm['name']+'-worker.txt')).write_text(proc.stdout+'\n'+proc.stderr)
            record('ssh-worker-qcow-'+vm['name'],proc.returncode==0 and real['qemu_name'] in proc.stdout and real['disk']['format']=='qcow2' and real['disk']['virtual-size']==vm['disk_bytes'] and bool(real['disk']['full-backing-filename']))
        ns='g5n'+sid[:10]
        known=(out/'guest_known_hosts').resolve()
        def ssh(vm,command,port=None):
            obj=vms[vm]
            argv=['ssh','-i',str(key),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(known)]
            if port is None:
                prefix=['sudo','-n','ip','netns','exec',ns]
                ip=obj['nics'][0]['ip']
            else:
                prefix=[];ip=cfg['gateway']['external_ip'];argv+=['-p',str(port)]
            return prefix+argv+[obj['guest']['username']+'@'+ip,command]
        def guest(vm,command,timeout=30):
            r=subprocess.run(ssh(vm,command),stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=timeout)
            return {'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
        for name in ('vm1','vm3','vm4','vm5'):
            # Esperar hasta que cloud-init cree usuario y claves; READY es estado del hipervisor.
            deadline=time.monotonic()+360
            while True:
                result=guest(name,'cloud-init status --wait && ip -br addr && command -v tcpdump && (arping -h 2>&1 || true) && sysctl -n net.ipv4.ip_forward',timeout=420)
                if result['returncode']==0 or time.monotonic()>deadline: break
                time.sleep(3)
            save(out/(name+'-guest.json'),result)
            record('guest-tools-'+name,result['returncode']==0 and '-B' in result['stdout'] and '/tcpdump' in result['stdout'] and result['stdout'].strip().endswith('0'),result)
            for nic in vms[name]['nics']:
                r=guest(name,'cat /sys/class/net/%s/address; ip -4 -o addr show dev %s'%(nic['name'],nic['name']))
                record('nic-'+name+'-'+nic['name'],r['returncode']==0 and nic['mac'] in r['stdout'] and nic['ip']+'/' in r['stdout'],r)
        for net in plan['networks']:
            if not net['name'].startswith('link'): continue
            peers=[(v,n) for v in plan['vms'] for n in v['nics'] if n['network']==net['name']]
            peers.sort(key=lambda vn:vn[0]['guest']['os']!='ubuntu')
            (source,nic),(target,tnic)=peers
            r=guest(source['name'],'ping -c 3 -W 2 -I %s %s'%(nic['name'],tnic['ip']))
            record('ping-'+net['name'],r['returncode']==0,r)
        # Capturas simultáneas. Cada ronda filtra la MAC de la NIC emisora de VM4.
        for peer in ('vm1','vm3','vm5'):
            source_nic=next(n for n in vms['vm4']['nics'] if n['name']=='to-'+peer)
            captures={}; threads=[]
            try:
                for dest in ('vm1','vm3','vm5'):
                    packet_filter='arp and ether src '+source_nic['mac']+' and ether dst ff:ff:ff:ff:ff:ff'
                    command='sudo -n timeout 10 tcpdump -l -nn -e -i to-vm4 '+shlex.quote(packet_filter)
                    proc=subprocess.Popen(ssh(dest,command),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
                    item={'process':proc,'ready':threading.Event(),'lines':[]}; captures[dest]=item
                    def reader(item=item):
                        for line in item['process'].stdout:
                            item['lines'].append(line)
                            if 'listening on' in line:item['ready'].set()
                    thread=threading.Thread(target=reader,daemon=True);thread.start();threads.append(thread)
                record('listeners-ready-'+peer,all(item['ready'].wait(12) and item['process'].poll() is None for item in captures.values()))
                sent=guest('vm4','sudo -n arping -B -c3 -I to-'+peer)
                # arping puede devolver 1 si nadie responde al broadcast; se evalúan paquetes observados.
                save(out/('arping-'+peer+'.json'),sent)
                for dest,item in captures.items():
                    rc=item['process'].wait(timeout=20)
                    threads[list(captures).index(dest)].join(timeout=2)
                    text=''.join(item['lines']); (out/('broadcast-'+peer+'-at-'+dest+'.txt')).write_text(text)
                    count=sum(bool(re.search(r'\bARP\b',line)) for line in item['lines'])
                    record('broadcast-'+peer+'-at-'+dest,rc in (0,124) and count==(3 if dest==peer else 0),{'frames':count,'expected':3 if dest==peer else 0,'rc':rc})
            finally:
                for item in captures.values():
                    if item['process'].poll() is None:
                        item['process'].terminate();item['process'].wait(timeout=5)
        for name in ('vm1','vm3'):
            r=guest(name,'ping -c 3 -W 3 8.8.8.8');record('internet-'+name,r['returncode']==0,r)
            pub=next(x for x in plan['publications'] if x['vm']==name)
            r=subprocess.run(ssh(name,'hostname; id',pub['external_port']),stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=30)
            record('ssh-publicacion-desde-head-'+name,r.returncode==0 and name in r.stdout,{'stdout':r.stdout,'stderr':r.stderr})
        for name in ('vm4','vm5'):
            r=guest(name,'ip -4 route; ping -c 2 -W 2 8.8.8.8')
            record('sin-internet-'+name,r['returncode']!=0 and 'default ' not in r['stdout'],r)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            capture=pool.submit(backend.call,cfg['switch']['name'],'qinq_capture')
            for _ in range(4):guest('vm4','ping -c 3 -W 1 -I to-vm3 192.168.34.10')
            trace=capture.result()
        save(out/'qinq.json',trace)
        record('qinq-ofs',bool(re.search(r'vlan\s+%s.*vlan\s+134'%plan['svid'],trace.get('stdout',''),re.I)),trace)
        consoles={}
        for name in ('vm1','vm3','vm4','vm5'):
            c=call('POST','/v1/slices/%s/vms/%s/console'%(sid,name),{'ttl':30});consoles[name]=c
            record('vnc-rfb-'+name,rfb(c['token']))
        record('vnc-rechaza-token-invalido',not rfb('invalid-ex1-token'))
        time.sleep(max(0,max(c['expires_at'] for c in consoles.values())-time.time()+2))
        record('vnc-token-expirado',not rfb(consoles['vm1']['token']))
        report['status']='AUTOMATED_PASS_MANUAL_PENDING'
    except Exception as exc:
        report['status']='FAILED';report['error']=str(exc);print(str(exc),file=sys.stderr)
    finally:
        report['finished_at']=time.time();save(out/'resultado.json',report)
        print('Evidencias: '+str(out.resolve()))
    return 0 if report['status']=='AUTOMATED_PASS_MANUAL_PENDING' else 1


if __name__=='__main__':
    sys.exit(main())
