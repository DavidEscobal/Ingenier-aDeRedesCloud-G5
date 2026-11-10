import { useCallback, useEffect, useState } from 'react'
import { Api } from '../api.js'

// Alumnos asignados a un slice: el profesor dueño (o el admin) asigna y retira. IAM decide los permisos.
export default function Assignments({ slice }) {
  const [assigned, setAssigned] = useState(null)
  const [students, setStudents] = useState([])
  const [choice, setChoice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [current, all] = await Promise.all([Api.assignments(slice.id), Api.students(slice.course_id)])
      setAssigned(current)
      setStudents(all)
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [slice.id, slice.course_id])
  useEffect(() => { load() }, [load])

  const available = students.filter((s) => !(assigned || []).some((a) => a.id === s.id))
  useEffect(() => { setChoice(available[0]?.id || '') }, [assigned, students]) // eslint-disable-line react-hooks/exhaustive-deps

  async function run(action) {
    setBusy(true)
    setError('')
    try {
      setAssigned(await action())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel assignments">
      <h2>Alumnos asignados</h2>
      <p className="muted small">Los alumnos asignados ven este slice en «Mis slices» y pueden abrir la consola de sus VMs. No pueden borrarlo.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {assigned === null ? <p className="muted">Cargando…</p> : (
        assigned.length === 0 ? <p className="muted">Nadie asignado todavía.</p> : (
          <ul className="people">
            {assigned.map((a) => (
              <li key={a.id}>
                <span><strong>{a.display_name}</strong> <span className="muted small">@{a.username}</span></span>
                <button className="link danger-text" disabled={busy}
                        onClick={() => run(() => Api.unassign(slice.id, a.id))}>Quitar</button>
              </li>
            ))}
          </ul>
        )
      )}
      <div className="inline assign-row">
        <select value={choice} onChange={(e) => setChoice(e.target.value)} disabled={!available.length || busy}>
          {available.length === 0
            ? <option value="">{students.length ? 'Todos los alumnos del curso ya están asignados' : 'No hay alumnos en el curso'}</option>
            : available.map((s) => <option key={s.id} value={s.id}>{s.display_name} (@{s.username})</option>)}
        </select>
        <button onClick={() => run(() => Api.assign(slice.id, choice))} disabled={!choice || busy}>Asignar</button>
      </div>
    </div>
  )
}
