import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Api } from '../api.js'
import osLineal from '../templates/os-lineal-1g.json'

// Catálogo provisional hasta el topology-manager (paso 6): plantillas fijas versionadas en el repo.
const TEMPLATES = [
  { id: 'os-lineal-1g', label: 'Lineal de 3 VMs (OpenStack, CirrOS)', spec: osLineal },
]

export default function NewSlice() {
  const navigate = useNavigate()
  const [courses, setCourses] = useState(null)
  const [course, setCourse] = useState('')
  const [templateId, setTemplateId] = useState(TEMPLATES[0].id)
  const [name, setName] = useState(TEMPLATES[0].spec.name)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Api.courses()
      .then((list) => {
        setCourses(list)
        if (list.length) setCourse(list[0].id)
      })
      .catch((err) => setError(err.message))
  }, [])

  const template = TEMPLATES.find((t) => t.id === templateId)
  const spec = useMemo(() => ({ ...template.spec, name }), [template, name])
  const totals = spec.vms.reduce((a, vm) => ({ vcpus: a.vcpus + vm.vcpus, ram: a.ram + vm.memory_mb, disk: a.disk + vm.disk_gb }),
    { vcpus: 0, ram: 0, disk: 0 })

  async function submit(event) {
    event.preventDefault()
    if (!course) return setError('Elige un curso.')
    if (!/^[a-z][a-z0-9-]{0,31}$/.test(name)) return setError('Nombre: empieza con letra; solo minúsculas, números y guiones (máx. 32).')
    setBusy(true)
    setError('')
    try {
      const accepted = await Api.createSlice(course, spec)
      navigate('/slices/' + accepted.slice_id)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <section>
      <Link to="/slices" className="back">← Mis slices</Link>
      <div className="page-head">
        <div>
          <h1>Nuevo slice</h1>
          <p className="sub">Elige una plantilla y el curso. Para dibujar tu propia topología usa <Link to="/topologias/nueva">el editor</Link>.</p>
        </div>
      </div>

      <form className="form-grid" onSubmit={submit} noValidate>
        <div className="panel">
          <label>
            Curso
            <select value={course} onChange={(e) => { setCourse(e.target.value); setError('') }} disabled={!courses?.length}>
              {courses === null && <option>Cargando…</option>}
              {courses?.length === 0 && <option>No estás matriculado en ningún curso</option>}
              {courses?.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.name}</option>)}
            </select>
          </label>
          <label>
            Plantilla
            <select value={templateId} onChange={(e) => { setTemplateId(e.target.value); setName(TEMPLATES.find((t) => t.id === e.target.value).spec.name) }}>
              {TEMPLATES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
            </select>
          </label>
          <label>
            Nombre del slice
            <input value={name} onChange={(e) => { setName(e.target.value.toLowerCase()); setError('') }} />
          </label>
          <div className="provider-choice">
            <span>Proveedor</span>
            <label className="radio"><input type="radio" checked readOnly /> OpenStack</label>
            <label className="radio disabled" title="Falta la configuración Linux de fase 2">
              <input type="radio" disabled /> Linux <small>(próximamente)</small>
            </label>
          </div>
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit" disabled={busy || !courses?.length}>{busy ? 'Enviando…' : 'Desplegar slice'}</button>
        </div>

        <div className="panel">
          <h2>Vista previa</h2>
          <p className="muted small">{spec.vms.length} VMs · {totals.vcpus} vCPU · {totals.ram} MB RAM · {totals.disk} GB disco</p>
          <table className="table compact">
            <thead><tr><th>VM</th><th>Imagen</th><th>vCPU</th><th>RAM</th><th>Disco</th><th>Interfaces</th></tr></thead>
            <tbody>
              {spec.vms.map((vm) => (
                <tr key={vm.name}>
                  <td>{vm.name}</td><td>{vm.image}</td><td>{vm.vcpus}</td><td>{vm.memory_mb} MB</td><td>{vm.disk_gb} GB</td>
                  <td className="mono small">{vm.nics.map((n) => `${n.network} ${n.ip || 'DHCP'}`).join(' · ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3>Redes</h3>
          <ul className="nets">
            {spec.networks.map((n) => <li key={n.name}><strong>{n.name}</strong> <span className="mono">{n.cidr}</span>{n.dhcp ? ' · DHCP' : ''}</li>)}
          </ul>
        </div>
      </form>
    </section>
  )
}
