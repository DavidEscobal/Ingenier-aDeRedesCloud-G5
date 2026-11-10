import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Api } from '../api.js'
import { ConfirmDialog, FINAL, formatDate, ProviderLabel, StatusBadge, usePolling } from '../components.jsx'

const EVENT_LABEL = {
  ACCEPTED: 'Solicitud aceptada', STARTED: 'Inicio', OS_CREATED: 'Recurso creado', OS_PLACED: 'Ubicación de VMs',
  OS_DELETED: 'Recurso borrado', READY: 'Listo', DELETED: 'Borrado', FAILED: 'Falló', FAILED_CLEANED: 'Falló (limpiado)',
  CLEANED: 'Limpieza',
}

export default function SliceDetail({ user }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const [slice, setSlice] = useState(null)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)

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

  if (error && !slice) {
    return (
      <section>
        <p className="error" role="alert">{error}</p>
        <Link to="/slices">← Volver</Link>
      </section>
    )
  }
  if (!slice) return <p className="muted">Cargando…</p>

  const deletable = ['READY', 'FAILED_CLEANED', 'FAILED', 'ERROR'].includes(slice.status)
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
