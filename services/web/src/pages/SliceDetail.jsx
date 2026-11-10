import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Api } from '../api.js'
import { ConfirmDialog, FINAL, formatDate, ProviderLabel, StatusBadge, usePolling } from '../components.jsx'
import Assignments from './Assignments.jsx'

const EVENT_LABEL = {
  ACCEPTED: 'Solicitud aceptada', STARTED: 'Inicio', OS_CREATED: 'Recurso creado', OS_PLACED: 'Ubicación de VMs',
  OS_DELETED: 'Recurso borrado', READY: 'Listo', DELETED: 'Borrado', FAILED: 'Falló', FAILED_CLEANED: 'Falló (limpiado)',
  CLEANED: 'Limpieza', CONSOLE: 'Consola solicitada', START: 'Inicio de operación',
}

// La URL de Nova llega como /console/vnc_auto.html?path=?token=…; el WebSocket debe ir también por /console/.
function consoleUrl(raw) {
  const url = new URL(raw, window.location.origin)
  const path = url.searchParams.get('path')
  if (url.pathname.startsWith('/console/') && path && !path.startsWith('console/')) {
    url.searchParams.set('path', 'console/' + path.replace(/^\//, ''))
  }
  return url.toString()
}

export default function SliceDetail({ user }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [slice, setSlice] = useState(null)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [opening, setOpening] = useState('')

  const load = useCallback(async () => {
    try {
      setSlice(await Api.slice(id))
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [id])

  useEffect(() => { load() }, [load])
  usePolling(load, 3000, slice && !FINAL.has(slice.status))

  async function remove() {
    setBusy(true)
    try {
      await Api.deleteSlice(id)
      setConfirm(false)
      await load()
    } catch (err) {
      setError(err.message)
      setConfirm(false)
    } finally {
      setBusy(false)
    }
  }

  async function openConsole(vm) {
    // La pestaña se abre en el mismo clic (evita el bloqueo de ventanas emergentes) y luego recibe la URL.
    const tab = window.open('about:blank', '_blank')
    setOpening(vm)
    setError('')
    try {
      const { url } = await Api.console(id, vm)
      if (tab) {
        tab.opener = null
        tab.location.href = consoleUrl(url)
      } else {
        window.location.href = consoleUrl(url)
      }
    } catch (err) {
      if (tab) tab.close()
      setError(`Consola de ${vm}: ${err.message}`)
    } finally {
      setOpening('')
    }
  }

  if (error && !slice) {
    return (
      <section>
        <p className="error" role="alert">{error}</p>
        <Link to="/slices">← Volver</Link>
      </section>
    )
  }
  if (!slice) return <p className="muted">Cargando…</p>

  const deletable = slice.can_manage && ['READY', 'FAILED_CLEANED', 'FAILED', 'ERROR'].includes(slice.status)
  return (
    <section>
      <Link to="/slices" className="back">← {user.role === 'admin' ? 'Todos los slices' : 'Mis slices'}</Link>
      <div className="page-head">
        <div>
          <h1>{slice.name || 'Slice'} <StatusBadge status={slice.status} /></h1>
          <p className="sub mono">{slice.id}</p>
        </div>
        {deletable && <button className="danger" onClick={() => setConfirm(true)}>Borrar slice</button>}
      </div>
      {error && <p className="error" role="alert">{error}</p>}

      <dl className="facts">
        <div><dt>Proveedor</dt><dd><ProviderLabel provider={slice.provider} /></dd></div>
        <div><dt>Curso</dt><dd>{slice.course_id}</dd></div>
        <div><dt>Dueño</dt><dd>{slice.owner}</dd></div>
        <div><dt>Creado</dt><dd>{formatDate(slice.created_at)}</dd></div>
      </dl>

      {slice.vms?.length > 0 && slice.status !== 'DELETED' && (
        <>
          <h2>Máquinas virtuales</h2>
          <table className="table compact">
            <thead><tr><th>VM</th><th>Imagen</th><th>vCPU</th><th>RAM</th><th>Disco</th><th>Redes</th><th></th></tr></thead>
            <tbody>
              {slice.vms.map((vm) => (
                <tr key={vm.name}>
                  <td><strong>{vm.name}</strong></td><td>{vm.image}</td><td>{vm.vcpus}</td><td>{vm.memory_mb} MB</td>
                  <td>{vm.disk_gb} GB</td><td className="mono small">{vm.networks.join(' · ')}</td>
                  <td className="actions">
                    {slice.status === 'READY' && slice.provider === 'openstack'
                      ? <button className="ghost" onClick={() => openConsole(vm.name)} disabled={opening === vm.name}>
                          {opening === vm.name ? 'Abriendo…' : 'Consola'}</button>
                      : <span className="muted small">{slice.status === 'READY' ? 'Consola: solo OpenStack por ahora' : ''}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {slice.status === 'READY' && <p className="hint">La consola se abre en otra pestaña. El enlace de Nova caduca en pocos minutos: si expira, vuelve a pulsar Consola.</p>}
        </>
      )}

      {slice.assignable && slice.status !== 'DELETED' && <Assignments slice={slice} />}
      {!slice.can_manage && (
        <p className="notice">Slice asignado por {slice.owner}. Puedes ver su estado y abrir la consola de sus VMs.</p>
      )}

      {!FINAL.has(slice.status) && (
        <p className="progress">La operación está en curso; esta página se actualiza cada 3 segundos.</p>
      )}

      <h2>Historial de la operación</h2>
      {slice.events.length === 0 ? <p className="muted">Sin eventos todavía.</p> : (
        <ol className="timeline">
          {slice.events.map((e) => (
            <li key={e.seq} className={'ev ev-' + (e.event || '').toLowerCase()}>
              <span className="ev-time">{e.timestamp ? new Date(e.timestamp * 1000).toLocaleTimeString('es-PE') : ''}</span>
              <span className="ev-name">{EVENT_LABEL[e.event] || e.event}</span>
              <span className="ev-detail">{e.detail}</span>
            </li>
          ))}
        </ol>
      )}

      {confirm && (
        <ConfirmDialog title="Borrar slice" confirmLabel="Borrar" busy={busy}
                       onConfirm={remove} onCancel={() => setConfirm(false)}>
          <p>Se eliminarán todas las VMs, redes y puertos de <strong>{slice.name}</strong>. No se puede deshacer.</p>
        </ConfirmDialog>
      )}
      {slice.status === 'DELETED' && (
        <p className="muted">Este slice fue borrado. <button className="link" onClick={() => navigate('/slices')}>Volver a la lista</button></p>
      )}
    </section>
  )
}
