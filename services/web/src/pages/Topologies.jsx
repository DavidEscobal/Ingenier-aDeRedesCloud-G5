import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Api } from '../api.js'
import { ConfirmDialog, formatDate } from '../components.jsx'
import { download } from '../topology.js'

export default function Topologies() {
  const [drafts, setDrafts] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [toDelete, setToDelete] = useState(null)
  const [busy, setBusy] = useState(false)
  const fileInput = useRef(null)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    try {
      setDrafts(await Api.drafts())
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [])
  useEffect(() => { load() }, [load])

  async function exportDraft(id) {
    try {
      const draft = await Api.draft(id)
      download(draft.topology)
    } catch (err) {
      setError(err.message)
    }
  }

  async function importFile(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setError('')
    setNotice('')
    try {
      if (file.size > 512 * 1024) throw new Error('El archivo supera 512 KB.')
      let topology
      try {
        topology = JSON.parse(await file.text())
      } catch {
        throw new Error('El archivo no es un JSON válido.')
      }
      const check = await Api.validateTopology(topology)
      if (!check.valid) throw new Error('No se puede importar: ' + check.problems.join('; '))
      const draft = await Api.createDraft(topology)
      setNotice(`Importada «${draft.name}» (${draft.nodes} VMs, ${draft.segments} segmentos).`)
      navigate('/topologias/' + draft.id)
    } catch (err) {
      setError(err.message)
    }
  }

  async function confirmDelete() {
    setBusy(true)
    try {
      await Api.deleteDraft(toDelete.id)
      setToDelete(null)
      await load()
    } catch (err) {
      setError(err.message)
      setToDelete(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Topologías</h1>
          <p className="sub">Borradores guardados para editar después, exportar, importar o desplegar como slice.</p>
        </div>
        <div className="head-actions">
          <button className="ghost" onClick={() => fileInput.current?.click()}>Importar JSON</button>
          <input ref={fileInput} type="file" accept="application/json,.json" hidden onChange={importFile} />
          <Link className="button" to="/topologias/nueva">+ Nueva topología</Link>
        </div>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="notice">{notice}</p>}
      {drafts === null && !error && <p className="muted">Cargando…</p>}
      {drafts?.length === 0 && (
        <div className="empty">
          <p>Aún no tienes topologías guardadas. <Link to="/topologias/nueva">Crea una</Link> o importa un JSON.</p>
        </div>
      )}
      {drafts?.length > 0 && (
        <table className="table">
          <thead><tr><th>Nombre</th><th>VMs</th><th>Segmentos</th><th>Versión</th><th>Actualizado</th><th></th></tr></thead>
          <tbody>
            {drafts.map((d) => (
              <tr key={d.id}>
                <td><Link to={'/topologias/' + d.id}>{d.name}</Link></td>
                <td>{d.nodes}</td>
                <td>{d.segments}</td>
                <td>v{d.version}</td>
                <td>{formatDate(d.updated_at)}</td>
                <td className="actions">
                  <Link to={'/topologias/' + d.id}>Editar</Link>
                  <button className="link" onClick={() => exportDraft(d.id)}>Exportar</button>
                  <button className="link danger-text" onClick={() => setToDelete(d)}>Borrar</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {toDelete && (
        <ConfirmDialog title="Borrar topología" confirmLabel="Borrar" busy={busy}
                       onConfirm={confirmDelete} onCancel={() => setToDelete(null)}>
          <p>Se borrará el borrador <strong>{toDelete.name}</strong>. Los slices ya desplegados no se ven afectados.</p>
        </ConfirmDialog>
      )}
    </section>
  )
}
