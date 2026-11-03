"""Ejecución recuperable de trabajos; los pasos concretos los aporta el driver del proveedor."""
import threading
from .domain import provider_of
from .drivers.base import OpContext


class Engine:
    def __init__(self, store, backend):
        self.store, self.backend = store, backend
        self.cfg = store.config
        self.drivers = store.drivers
        self.stop = threading.Event()
        self.threads = []

    def driver(self, plan):
        return self.drivers[provider_of(plan)]

    def context(self, plan, jid):
        return OpContext(self.store, jid, plan['id'], self.stop)

    def participants(self, plan):
        return self.driver(plan).participants(plan)

    def deploy(self, plan, jid):
        detail = self.driver(plan).deploy(plan, self.context(plan, jid))
        self.store.status(plan['id'], 'READY')
        self.store.event(plan['id'], jid, 'READY', detail)

    def cleanup(self, plan, jid, final_status):
        sid = plan['id']
        self.driver(plan).cleanup(plan, self.context(plan, jid))
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
                self.driver(plan).stop(plan, self.context(plan, jid))
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
