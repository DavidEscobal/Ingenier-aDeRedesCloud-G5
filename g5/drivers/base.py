"""Contrato que todo driver de infraestructura cumple frente al núcleo del orquestador."""


class OpContext:
    """Lo que el Engine presta a un driver durante una operación: eventos y esperas cancelables."""
    def __init__(self, store, jid, sid, stop):
        self.store, self.jid, self.sid, self.stop = store, jid, sid, stop

    def event(self, name, detail=''):
        self.store.event(self.sid, self.jid, name, detail)

    def wait(self, seconds):
        self.stop.wait(seconds)


class ProviderDriver:
    """Un driver materializa planes de slice en una plataforma concreta.

    validate: normaliza y valida la solicitud (sin efectos).
    reserve:  dentro de la transacción de admisión, reserva lo propio del proveedor y completa el plan.
    deploy:   crea y verifica los recursos; devuelve un texto para el evento READY.
    cleanup:  elimina los recursos del slice; si falla, eleva excepción y no se liberan reservas.
    stop:     detiene las VMs conservando discos, redes y reservas.
    preflight: comprobación previa a aceptar una solicitud (sin efectos).
    inspect:  estado real observado de los recursos del slice (diagnóstico).
    console:  acceso temporal a la consola de una VM.
    """
    name = None

    def capabilities(self):
        return {}

    def preflight(self, spec):
        return None

    def inspect(self, plan, store):
        raise NotImplementedError

    def console(self, store, sid, vm_name):
        raise NotImplementedError

    def validate(self, spec):
        raise NotImplementedError

    def reserve(self, db, sid, plan):
        raise NotImplementedError

    def deploy(self, plan, ctx):
        raise NotImplementedError

    def cleanup(self, plan, ctx):
        raise NotImplementedError

    def stop(self, plan, ctx):
        raise NotImplementedError
