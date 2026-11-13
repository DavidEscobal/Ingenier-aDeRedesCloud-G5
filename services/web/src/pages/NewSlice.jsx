import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Api } from '../api.js'

// Nuevo slice = elegir una topología (predefinida o guardada en el editor), el proveedor, el nombre y el curso.
// El catálogo (formas, tamaños, imágenes, proveedores) lo da el topology-manager: nada fijo en este código.
const IDENT = /^[a-z][a-z0-9-]{0,31}$/
const PROVIDER_LABEL = { openstack: 'OpenStack', linux: 'Linux (clúster server1–3)' }

export default function NewSlice() {
  const navigate = useNavigate()
  const location = useLocation()
  const fromEditor = location.state?.topology || null // atajo desde el editor ("Desplegar")

  const [courses, setCourses] = useState(null)
  const [course, setCourse] = useState('')
  const [catalog, setCatalog] = useState(null)
  const [drafts, setDrafts] = useState([])
  const [source, setSource] = useState(fromEditor ? 'editor' : 'gen:lineal') // gen:<forma> | draft:<id> | editor
  const [n, setN] = useState(3)
  const [image, setImage] = useState('')
  const [size, setSize] = useState('small')
  const [provider, setProvider] = useState('openstack')
  const [name, setName] = useState(fromEditor?.name || 'lineal-3')
  const [topology, setTopology] = useState(fromEditor)
  const [preview, setPreview] = useState(null)
  const [imageNames, setImageNames] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([Api.courses(), Api.catalog(), Api.drafts()])
      .then(([cs, cat, ds]) => {
        setCourses(cs); if (cs.length) setCourse(cs[0].id)
        setCatalog(cat); setImage(cat.images?.[0] || 'cirros'); setSize(cat.sizes?.[0]?.id || 'small')
        setDrafts(ds)
      })
      .catch((err) => setError(err.message))
    // Imágenes reales del catálogo (D-15); si no responde, se queda la lista base del topology-manager.
    Api.images().then((list) => setImageNames(list.map((i) => i.name))).catch(() => setImageNames(null))
  }, [])

  const generator = source.startsWith('gen:') ? catalog?.generators.find((g) => g.id === source.slice(4)) : null

  // Obtener la topología elegida.
  useEffect(() => {
    if (!catalog) return
    let cancelled = false
    const done = (t) => { if (!cancelled) { setTopology(t); setError('') } }
    const fail = (err) => { if (!cancelled) { setTopology(null); setPreview(null); setError(err.message) } }
    if (source === 'editor') done(fromEditor)
    else if (source.startsWith('draft:')) Api.draft(source.slice(6)).then((d) => done(d.topology)).catch(fail)
    else if (generator) {
      const count = Math.min(Math.max(n, generator.min), generator.max)
      Api.generate(generator.id, count, { image, size, name: `${generator.id}-${count}` }).then(done).catch(fail)
    }
    return () => { cancelled = true }
  }, [catalog, source, n, image, size]) // eslint-disable-line react-hooks/exhaustive-deps

  // Vista previa = la especificación compilada para el proveedor elegido (lo mismo que se enviará).
  useEffect(() => {
    if (!topology) return
    let cancelled = false
    Api.compile(topology, provider, IDENT.test(name) ? name : undefined)
      .then((spec) => { if (!cancelled) { setPreview(spec); setError('') } })
      .catch((err) => { if (!cancelled) { setPreview(null); setError(err.message) } })
    return () => { cancelled = true }
  }, [topology, provider]) // eslint-disable-line react-hooks/exhaustive-deps

  function pickSource(value) {
    setSource(value)
    if (value.startsWith('gen:')) setName(`${value.slice(4)}-${n}`)
    else if (value.startsWith('draft:')) setName(drafts.find((d) => 'draft:' + d.id === value)?.name || name)
  }

  async function submit(event) {
    event.preventDefault()
    if (!course) return setError('Elige un curso.')
    if (!IDENT.test(name)) return setError('Nombre: empieza con letra; solo minúsculas, números y guiones (máx. 32).')
    if (!topology) return setError('Elige una topología válida.')
    setBusy(true)
    setError('')
    try {
      const spec = await Api.compile(topology, provider, name)
      const accepted = await Api.createSlice(course, spec)
      navigate('/slices/' + accepted.slice_id)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const vms = preview?.vms || []
  const totals = vms.reduce((a, vm) => ({ vcpus: a.vcpus + vm.vcpus, ram: a.ram + vm.memory_mb, disk: a.disk + vm.disk_gb }),
    { vcpus: 0, ram: 0, disk: 0 })

  return (
    <section>
      <Link to="/slices" className="back">← Mis slices</Link>
      <div className="page-head">
        <div>
          <h1>Nuevo slice</h1>
          <p className="sub">Elige una topología predefinida o una que hayas guardado en <Link to="/topologias">Topologías</Link>,
            el proveedor y el curso.</p>
        </div>
      </div>

      <form className="form-grid" onSubmit={submit} noValidate>
        <div className="panel">
          <label>Curso
            <select value={course} onChange={(e) => { setCourse(e.target.value); setError('') }} disabled={!courses?.length}>
              {courses === null && <option>Cargando…</option>}
              {courses?.length === 0 && <option>No estás matriculado en ningún curso</option>}
              {courses?.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.name}</option>)}
            </select>
          </label>
          <label>Topología
            <select value={source} onChange={(e) => pickSource(e.target.value)} disabled={!catalog}>
              {fromEditor && <option value="editor">Desde el editor: {fromEditor.name}</option>}
              <optgroup label="Predefinidas">
                {catalog?.generators.map((g) => <option key={g.id} value={'gen:' + g.id}>{g.label}</option>)}
              </optgroup>
              {drafts.length > 0 && (
                <optgroup label="Mis topologías">
                  {drafts.map((d) => <option key={d.id} value={'draft:' + d.id}>{d.name}</option>)}
                </optgroup>
              )}
            </select>
          </label>
          {generator && (
            <div className="upload-grid">
              <label>Nodos ({generator.min}–{generator.max})
                <input type="number" min={generator.min} max={generator.max} value={n}
                  onChange={(e) => { const v = Number(e.target.value) || generator.min; setN(v); setName(`${generator.id}-${v}`) }} />
              </label>
              <label>Imagen
                <select value={image} onChange={(e) => setImage(e.target.value)}>
                  {[...new Set([...(imageNames || catalog.images), image])].map((i) => <option key={i} value={i}>{i}</option>)}
                </select>
              </label>
              <label>Tamaño de cada VM
                <select value={size} onChange={(e) => setSize(e.target.value)}>
                  {catalog.sizes.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </label>
            </div>
          )}
          {!generator && <p className="muted small">Imagen, tamaño e Internet de cada VM se definen en el editor de la topología.</p>}
          <label>Nombre del slice
            <input value={name} onChange={(e) => { setName(e.target.value.toLowerCase()); setError('') }} />
          </label>
          <label>Proveedor
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {(catalog?.providers || ['openstack']).map((p) => <option key={p} value={p}>{PROVIDER_LABEL[p] || p}</option>)}
            </select>
          </label>
          {provider === 'linux' && (
            <p className="muted small">Linux: solo imágenes CirrOS; las VMs se reparten por turnos entre server1–3 (provisional,
              hasta definir el placement).</p>
          )}
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit" disabled={busy || !courses?.length || !preview}>{busy ? 'Enviando…' : 'Desplegar slice'}</button>
        </div>

        <div className="panel">
          <h2>Vista previa</h2>
          {!preview && !error && <p className="muted">Preparando…</p>}
          {preview && (
            <>
              <p className="muted small">{PROVIDER_LABEL[provider] || provider} · {vms.length} VMs · {totals.vcpus} vCPU ·
                {' '}{totals.ram} MB RAM · {totals.disk} GB disco</p>
              <table className="table compact">
                <thead><tr><th>VM</th><th>Imagen</th><th>vCPU</th><th>RAM</th><th>Disco</th><th>Interfaces</th></tr></thead>
                <tbody>
                  {vms.map((vm) => (
                    <tr key={vm.name}>
                      <td>{vm.name}{vm.internet ? ' · Internet' : ''}</td><td>{vm.image}</td><td>{vm.vcpus}</td>
                      <td>{vm.memory_mb} MB</td><td>{vm.disk_gb} GB</td>
                      <td className="mono small">{vm.nics.map((x) => `${x.network} ${x.ip || 'DHCP'}`).join(' · ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <h3>Redes</h3>
              <ul className="nets">
                {preview.networks.map((x) => <li key={x.name}><strong>{x.name}</strong> <span className="mono">{x.cidr}</span></li>)}
              </ul>
            </>
          )}
        </div>
      </form>
    </section>
  )
}
