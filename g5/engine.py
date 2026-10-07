"""Ejecución recuperable: planes inmutables, IDs estables, compensación selectiva."""
import concurrent.futures
import threading
import time
from .backend import RemoteError
from .model import require


class Engine:
    def __init__(self, store, backend):
        self.store, self.backend = store, backend
        self.cfg = store.config
        self.stop = threading.Event()
        self.threads = []

    def participants(self, plan):
        return sorted({v['worker'] for v in plan['vms']} | {self.cfg['gateway']['name']})

    def retry(self, node, action, jid, log_sid, **params):
        for attempt in range(self.cfg['remote_retries']):
            try:
                return self.backend.call(node, action, **params)
            except RemoteError as exc:
                self.store.event(log_sid, jid, 'RETRY', '%s/%s intento %s: %s' % (node, action, attempt + 1, exc))
                if attempt + 1 == self.cfg['remote_retries']:
                    raise
                self.stop.wait(min(2**attempt, 8) * self.cfg.get('retry_delay', 1))

    def parallel(self, functions):
        # Esperar a TODOS antes de compensar: una tarea tardía no debe recrear recursos borrados.
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.cfg['parallel_nodes']) as pool:
            futures = [pool.submit(fn) for fn in functions]
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    errors.append(exc)
        if errors:
            raise RemoteError('; '.join(str(x) for x in errors))

    def deploy(self, plan, jid):
        sid = plan['id']
        switch = self.cfg['switch']['name']
        nodes = self.participants(plan)
        self.retry(switch, 'fabric_add', jid, sid, sid=sid, svid=plan['svid'])
        for node in nodes:
            self.retry(node, 'prepare', jid, sid, plan=plan)
        self.store.event(sid, jid, 'PREPARED', ','.join(nodes))

        def worker(node):
            for image in sorted({v['image'] for v in plan['vms'] if v['worker'] == node}):
                for attempt in range(self.cfg['remote_retries']):
                    try:
                        self.backend.transfer(node, image, self.store.directory / 'images' / (image + '.qcow2'))
                        break
                    except RemoteError as exc:
                        self.store.event(sid, jid, 'RETRY', '%s/image_receive intento %s: %s' % (node, attempt + 1, exc))
                        if attempt + 1 == self.cfg['remote_retries']:
                            raise
                        self.stop.wait(min(2**attempt, 8) * self.cfg.get('retry_delay', 1))
            self.retry(node, 'network', jid, sid, sid=sid)
        self.parallel([lambda node=node: worker(node) for node in nodes])
        self.retry(self.cfg['gateway']['name'], 'gateway', jid, sid, sid=sid)
        self.store.event(sid, jid, 'NETWORK_READY', 'QinQ, DHCP y política IPv4 aplicados')

        def start(node):
            for vm in plan['vms']:
                if vm['worker'] == node:
                    self.retry(node, 'vm_ensure', jid, sid, sid=sid, vm_name=vm['name'])
                    if vm.get('guest', {}).get('os') == 'cirros':
                        self.retry(node, 'guest_setup', jid, sid, sid=sid, vm_name=vm['name'])
        self.parallel([lambda node=node: start(node) for node in sorted({v['worker'] for v in plan['vms']})])
        for node in nodes:
            result = self.retry(node, 'inspect', jid, sid, sid=sid)
            require(result['ok'], 'Estado real inconsistente en ' + node, 503)
        self.store.status(sid, 'READY')
        self.store.event(sid, jid, 'READY', 'QEMU y red creados; no implica que el SO invitado haya terminado de arrancar')

    def cleanup(self, plan, jid, final_status):
        sid = plan['id']
        self.parallel([lambda node=node: self.retry(node, 'delete', jid, sid, sid=sid) for node in self.participants(plan)])
        self.retry(self.cfg['switch']['name'], 'fabric_delete', jid, sid, sid=sid)
        self.store.release(sid, final_status)
        self.store.event(sid, jid, final_status, 'Eliminación confirmada en todos los destinos; reservas liberadas')

    def process_one(self):
        job = self.store.claim()
        if not job:
            return False
        sid, jid = job['slice_id'], job['id']
        plan = self.store.get_slice(sid)['plan']
        self.store.event(sid, jid, 'START', job['action'])
        try:
            if job['action'] == 'delete':
                self.cleanup(plan, jid, 'DELETED')
            elif job['action'] == 'stop':
                self.parallel([lambda v=v: self.retry(v['worker'], 'vm_stop', jid, sid, sid=sid, vm_name=v['name']) for v in plan['vms']])
                self.store.status(sid, 'STOPPED')
                self.store.event(sid, jid, 'STOPPED', 'Discos, redes y reservas conservados')
            else:
                self.store.status(sid, 'DEPLOYING')
                self.deploy(plan, jid)
            self.store.finish(jid, 'SUCCEEDED')
        except Exception as exc:
            detail = str(exc)
            # Una reconciliación fallida nunca destruye discos de un slice existente.
            if job['action'] == 'create':
                try:
                    self.cleanup(plan, jid, 'FAILED_CLEANED')
                except Exception as cleanup_error:
                    detail += '; limpieza pendiente: ' + str(cleanup_error)
                    self.store.status(sid, 'ERROR_CLEANUP')
            elif job['action'] == 'delete':
                self.store.status(sid, 'ERROR_CLEANUP')
            else:
                self.store.status(sid, 'ERROR')
            self.store.event(sid, jid, 'FAILED', detail)
            self.store.finish(jid, 'FAILED', detail)
        return True

    def start(self):
        self.store.recover()
        def worker():
            while not self.stop.is_set():
                if not self.process_one():
                    self.stop.wait(0.25)
        for i in range(self.cfg['parallel_jobs']):
            thread = threading.Thread(target=worker, name='g5-job-%s' % i, daemon=True)
            thread.start(); self.threads.append(thread)

    def close(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=5)
