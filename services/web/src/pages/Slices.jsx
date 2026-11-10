import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Api } from '../api.js'
import { canCreate, ConfirmDialog, FINAL, formatDate, ProviderLabel, StatusBadge, usePolling } from '../components.jsx'

export default function Slices({ user }) {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [toDelete, setToDelete] = useState(null)
  const [busy, setBusy] = useState(false)
  const [showDeleted, setShowDeleted] = useState(false)

  const load = useCallback(async () => {
    try {
      setRows(await Api.slices())
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => { load() }, [load])
  const changing = (rows || []).some((r) => !FINAL.has(r.status))
  usePolling(load, 4000, changing)

  async function confirmDelete() {
    setBusy(true)
    try {
      await Api.deleteSlice(toDelete.id)
      setToDelete(null)
      await load()
    } catch (err) {
      setError(err.message)
      setToDelete(null)
    } finally {
      setBusy(false)
    }
  }

  const visible = (rows || []).filter((r) => showDeleted || r.status !== 'DELETED')
  const hidden = (rows || []).length - visible.length
  const admin = user.role === 'admin'

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>{admin ? 'Todos los slices' : 'Mis slices'}</h1>
          <p className="sub">
            {admin ? 'Slices de todos los usuarios, con su dueño y curso.' : 'Slices que creaste. El estado se actualiza solo mientras cambia.'}
          </p>
        </div>
        {canCreate(user) && <Link className="button" to="/slices/nuevo">+ Nuevo slice</Link>}
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {rows === null && !error && <p className="muted">Cargando…</p>}

      {rows !== null && visible.length === 0 && (
        <div className="empty">
          {user.role === 'student'
            ? <p>Aún no tienes slices asignados. Cuando tu profesor te asigne uno, aparecerá aquí.</p>
            : <p>No hay slices activos. {canCreate(user) && <Link to="/slices/nuevo">Crea el primero</Link>}</p>}
        </div>
      )}

      {visible.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Nombre</th><th>Proveedor</th><th>Curso</th>{admin && <th>Dueño</th>}<th>Estado</th><th>Creado</th><th></th>
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.id}>
                <td><Link to={'/slices/' + r.id}>{r.name || r.id.slice(0, 8)}</Link><div className="mono small">{r.id.slice(0, 8)}</div></td>
                <td><ProviderLabel provider={r.provider} /></td>
                <td>{r.course_id}</td>
                {admin && <td>{r.owner}</td>}
                <td><StatusBadge status={r.status} /></td>
                <td>{formatDate(r.created_at)}</td>
                <td className="actions">
                  <Link to={'/slices/' + r.id}>Ver</Link>
                  {(admin || r.owner_id === user.id) && ['READY', 'FAILED_CLEANED', 'FAILED', 'ERROR'].includes(r.status) && (
                    <button className="link danger-text" onClick={() => setToDelete(r)}>Borrar</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {hidden > 0 && (
        <button className="link small" onClick={() => setShowDeleted(true)}>Mostrar {hidden} slice(s) borrado(s)</button>
      )}

      {toDelete && (
        <ConfirmDialog title="Borrar slice" confirmLabel="Borrar" busy={busy}
                       onConfirm={confirmDelete} onCancel={() => setToDelete(null)}>
          <p>Se eliminarán todas las VMs, redes y puertos de <strong>{toDelete.name}</strong> en {toDelete.provider === 'openstack' ? 'OpenStack' : 'el clúster Linux'}.</p>
          <p>Esta acción no se puede deshacer.</p>
        </ConfirmDialog>
      )}
    </section>
  )
}
