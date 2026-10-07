"""Regresiones de la topología y la guía de evaluación del EX1."""
import copy
import hashlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
from g5.agent import Agent, AgentError, cloud_documents
from g5.api import Application
from g5.backend import MemoryBackend
from g5.demo import process_table
from g5.model import Fault, disk_bytes, validate

ROOT=Path(__file__).resolve().parents[1]
HASH='$6$testsalt$'+'a'*86
PUBLIC='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDg5ZXgxZGVtbyBwdWJsaWMga2V5IGZvciB0ZXN0 test'


def resolved(kind='ex1'):
    spec=json.loads((ROOT/'templates'/(kind+'.json')).read_text())
    for vm in spec['vms']:
        vm['image']=hashlib.sha256(vm['image'].encode()).hexdigest()
        if vm['guest']['os']=='ubuntu':
            vm['guest'].update(username='ex1',password_hash=HASH,ssh_authorized_keys=[PUBLIC])
    for pub in spec['publications']:
        pub['allowed_sources']=['10.0.10.4/32','10.8.0.2/32']
    return spec


class EX1Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.cfg=json.loads((ROOT/'config/cluster.example.json').read_text());self.cfg['retry_delay']=0
        self.backend=MemoryBackend(self.cfg)
        self.app=Application(self.cfg,self.temp.name,[],backend=self.backend);self.store=self.app.store
        self.spec=resolved()
        with self.store.tx() as db:
            for family,size in [('ubuntu',2*1024**3),('cirros',40*1024**2)]:
                sha=hashlib.sha256(family.encode()).hexdigest()
                db.execute('INSERT INTO images VALUES(?,?,?,?,?)',(sha,family,100,size,time.time()))
                (self.store.directory/'images'/(sha+'.qcow2')).write_bytes(b'test-only')
    def tearDown(self):
        self.app.close();self.temp.cleanup()
    def create(self,spec=None,key='ex1-test-create'):
        return self.store.create('profesor',key,validate(spec or self.spec,self.cfg))
    def plan(self):
        job=self.create();return self.store.get_slice(job['slice_id'])['plan']
    def agent(self):
        c=dict(self.cfg['common'],**self.cfg['workers']['server1']);c['state_dir']=self.temp.name+'/worker';return Agent(c)
    def test_exact_vm_workers_flavors(self):
        plan=self.plan()
        self.assertEqual([(v['name'],v['worker']) for v in plan['vms']], [('vm1','server1'),('vm2','server2'),('vm3','server3'),('vm4','server1'),('vm5','server2'),('vm6','server3')])
        for v in plan['vms']:
            self.assertEqual((v['vcpus'],v['memory_mb']),(1,512))
            self.assertEqual(v['disk_gb'],2.2 if v['name'] in ('vm1','vm3','vm4','vm5') else 1)
        self.assertEqual(self.cfg['gateway']['name'],'server4')
    def test_edges_and_broadcast_domains(self):
        p=self.plan()
        expected={('vm1','vm2'),('vm2','vm3'),('vm1','vm4'),('vm3','vm4'),('vm4','vm5'),('vm5','vm6')}
        actual=set()
        for net in p['networks']:
            peers=tuple(v['name'] for v in p['vms'] if any(n['network']==net['name'] for n in v['nics']))
            if net['name'].startswith('link'):actual.add(peers)
        self.assertEqual(actual,expected)
        self.assertEqual(len({n['cvid'] for n in p['networks']}),8)
        vm4=next(v for v in p['vms'] if v['name']=='vm4')
        self.assertEqual({n['name'] for n in vm4['nics']},{'to-vm1','to-vm3','to-vm5'})
    def test_fractional_disk_exact_sector_size_and_invalid_values(self):
        self.assertEqual(disk_bytes(2.2),2362232320)
        self.assertEqual(disk_bytes(2.2,'GB'),2200000000)
        for value in (True,False,float('nan'),float('inf'),-1,'2.2',0):
            with self.assertRaises(Fault):disk_bytes(value)
    def test_larger_base_rejected_without_rounding_flavor(self):
        with self.store.tx() as db:db.execute("UPDATE images SET virtual_size=? WHERE name='ubuntu'",(3*1024**3,))
        with self.assertRaises(Fault):self.create()
        self.assertEqual(self.store.rows('SELECT * FROM allocations'),[])
    def test_publications_and_default_routes_only_vm1_vm3(self):
        p=self.plan();self.assertEqual({x['vm'] for x in p['publications']},{'vm1','vm3'})
        self.assertEqual({v['name'] for v in p['vms'] if v['internet']},{'vm1','vm3'})
        for vm in p['vms']:
            if vm['guest']['os']!='ubuntu':continue
            docs=cloud_documents(p,vm,1450)
            net=json.loads(docs['network-config'])['ethernets']
            defaults=[n for n,c in net.items() if 'gateway4' in c]
            self.assertEqual(defaults,['access0'] if vm['name'] in ('vm1','vm3') else [])
            for nic in vm['nics']:
                self.assertEqual(net[nic['name']]['match']['macaddress'],nic['mac'])
                self.assertFalse(net[nic['name']]['dhcp4'])
            data=json.loads(docs['user-data'].split('\n',1)[1])
            self.assertFalse(data['ssh_pwauth']);self.assertFalse(data['users'][0]['lock_passwd'])
    def test_lineal_and_ring_have_correct_degrees(self):
        for kind,nedges in [('lineal',5),('anillo',6)]:
            spec=validate(resolved(kind),self.cfg)
            self.assertEqual(sum(n['name'].startswith('link') for n in spec['networks']),nedges)
            degrees=[sum(n['network'].startswith('link') for n in vm['nics']) for vm in spec['vms']]
            self.assertEqual(degrees,[1,2,2,2,2,1] if kind=='lineal' else [2]*6)
    def test_full_six_vm_lifecycle_auto_gc(self):
        job=self.create();self.app.engine.process_one();sid=job['slice_id']
        self.assertEqual(self.store.get_slice(sid)['status'],'READY')
        self.assertEqual(sum(len(x['vms']) for x in self.backend.resources.values()),6)
        self.assertEqual(len(self.backend.images),5) # Ubuntu en tres workers; CirrOS en dos
        self.assertEqual(sum(action=='guest_setup' for _,action,_ in self.backend.calls),2)
        self.store.mutate(sid,'profesor',True,'delete-ex1-test','delete');self.app.engine.process_one()
        self.assertFalse(self.backend.images);self.assertFalse(self.backend.resources)
        self.assertEqual(self.store.rows('SELECT * FROM allocations'),[])
    def test_two_full_slices_admission_requires_capacity(self):
        self.create()
        spec=copy.deepcopy(self.spec);spec['publications']=[]
        with self.assertRaises(Fault):self.create(spec,'second-full-ex1')
        self.assertEqual(len(self.store.rows('SELECT * FROM allocations')),6)
    def test_retries_guest_setup_transient_failure(self):
        self.backend.failures[('server3','guest_setup')]=1
        job=self.create();self.app.engine.process_one()
        self.assertEqual(self.store.get_slice(job['slice_id'])['status'],'READY')
        self.assertTrue(any('guest_setup' in r['detail'] for r in self.store.rows("SELECT * FROM events WHERE event='RETRY'")))
    def test_nic_and_credentials_validation(self):
        for mutate in [lambda s:s['vms'][0]['nics'][1].update(name='access0'),lambda s:s['vms'][0]['guest'].update(password_hash='password'),lambda s:s['vms'][0]['guest'].update(ssh_authorized_keys=['ssh-ed25519 AAAAA\ncommand'])]:
            spec=copy.deepcopy(self.spec);mutate(spec)
            with self.assertRaises(Fault):validate(spec,self.cfg)
    def test_gc_retains_shared_base_until_last_reference(self):
        agent=self.agent();p=self.plan();sid=p['id'];agent.manifest_path(sid).write_text(json.dumps(p))
        sha=p['vms'][0]['image'];base=agent.root/'images'/(sha+'.qcow2');base.write_bytes(b'base')
        agent.cache_gc(all_unused=True);self.assertTrue(base.exists())
        agent.manifest_path(sid).unlink();self.assertEqual(agent.cache_gc(all_unused=True)['removed'],[sha])
    def test_gc_targeted_does_not_remove_other_unused_base(self):
        agent=self.agent();a='a'*64;b='b'*64
        for sha in (a,b):(agent.root/'images'/(sha+'.qcow2')).write_bytes(b'base')
        result=agent._gc(all_unused=True,candidates={a})
        self.assertEqual(result['removed'],[a]);self.assertTrue((agent.root/'images'/(b+'.qcow2')).exists())
    def test_process_report_does_not_invent_pids(self):
        p=self.plan();rows=process_table(p,{'nodes':{}})
        self.assertEqual(len(rows),6);self.assertTrue(all(v['pid'] is None and not v['running'] for v in rows))
    def test_head_gateway_supports_local_and_external_dnat(self):
        c=dict(self.cfg['common'],**self.cfg['gateway']);c['state_dir']=self.temp.name+'/gateway'
        hooks=Agent(c).firewall_plan(self.plan())[3]
        self.assertTrue(any(t=='nat' and chain=='PREROUTING' for t,chain,_ in hooks))
        self.assertTrue(any(t=='nat' and chain=='OUTPUT' for t,chain,_ in hooks))
    def test_remote_prepare_rejects_integer_truncation(self):
        p=self.plan();self.assertEqual(p['vms'][0]['disk_bytes'],2362232320)
        p['vms'][0]['disk_bytes']=2.2
        with self.assertRaises(AgentError):self.agent().prepare(p)


if __name__=='__main__':unittest.main()
