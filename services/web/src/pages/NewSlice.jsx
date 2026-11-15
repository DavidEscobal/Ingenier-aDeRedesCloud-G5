import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Api } from '../api.js'
import { NAME } from '../topology.js'

// Nuevo slice = elegir una topología (predefinida o guardada en el editor), el proveedor, el nombre y el curso.
// El catálogo (formas, tamaños, imágenes, proveedores) lo da el topology-manager: nada fijo en este código.
const PROVIDER_LABEL = { openstack: 'OpenStack', linux: 'Linux (clúster server1–3)', auto: 'Automático (el VM Placement elige)' }
const GUEST_USER = /^[a-z][a-z0-9_-]{0,30}$/

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
  const [zone, setZone] = useState('')
  const [zones, setZones] = useState([])
  const [name, setName] = useState(fromEditor?.name || 'lineal-3')
  const [topology, setTopology] = useState(fromEditor)
  const [preview, setPreview] = useState(null)
  const [imageNames, setImageNames] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // Acceso a las VMs Ubuntu (cloud-init). La contraseña solo vive en este formulario hasta enviarse.
  const [guestUser, setGuestUser] = useState('ubuntu')
  const [guestPassword, setGuestPassword] = useState('')
  const [guestConfirm, setGuestConfirm] = useState('')
  const [guestKey, setGuestKey] = useState('')

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

  // Zonas de disponibilidad del proveedor según el monitoreo (R4-I-04). Sin monitoreo: solo "cualquiera".
  useEffect(() => {
    let cancelled = false
    setZone('')
    Api.monitoringState(provider === 'auto' ? undefined : provider) // auto: zonas de ambos clústeres
      .then((st) => { if (!cancelled) setZones([...new Set(st.hosts.map((h) => h.zone).filter(Boolean))].sort()) })
      .catch(() => { if (!cancelled) setZones([]) })
    return () => { cancelled = true }
  }, [provider])

  // Vista previa = la especificación compilada para el proveedor elegido (lo mismo que se enviará).
  useEffect(() => {
    if (!topology) return
    let cancelled = false
    Api.compile(topology, provider, NAME.test(name) ? name : undefined)
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
    if (!NAME.test(name)) return setError('Nombre: empieza con letra; letras, números, _ o - (máx. 64). Ej.: Ex2_G5_test')
    if (!topology) return setError('Elige una topología válida.')
    let guest
    if (needsGuest) {
      if (!GUEST_USER.test(guestUser) || guestUser === 'root') return setError('Usuario de las VMs: minúsculas, números, _ o - (no root).')
      if (guestPassword.length < 8) return setError('La contraseña de las VMs debe tener al menos 8 caracteres.')
      if (guestPassword !== guestConfirm) return setError('Las contraseñas de las VMs no coinciden.')
      guest = { username: guestUser, password: guestPassword, ssh_authorized_keys: guestKey.split('\n').map((k) => k.trim()).filter(Boolean) }
    }
    setBusy(true)
    setError('')
    try {
      const spec = await Api.compile(topology, provider, name)
      const accepted = await Api.createSlice(course, spec, zone || undefined, guest)
      setGuestPassword(''); setGuestConfirm('')
      navigate('/slices/' + accepted.slice_id)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const vms = preview?.vms || []
  const needsGuest = vms.some((vm) => /ubuntu/i.test(vm.image || ''))
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
            <input value={name} onChange={(e) => { setName(e.target.value); setError('') }} />
          </label>
          <label>Proveedor
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {(catalog?.providers || ['openstack']).map((p) => <option key={p} value={p}>{PROVIDER_LABEL[p] || p}</option>)}
            </select>
          </label>
          <label>Zona de disponibilidad
            <select value={zone} onChange={(e) => setZone(e.target.value)}>
              <option value="">Cualquiera (el VM Placement elige el servidor)</option>
              {zones.map((z) => <option key={z} value={z}>{z}</option>)}
            </select>
          </label>
          <p className="muted small">
            El VM Placement (BCDP v2) ubica cada VM según los recursos libres; una VM con servidor fijado en el editor se
            respeta. Si no hay capacidad, el slice se rechaza con el motivo. Ver <Link to="/recursos">Recursos</Link>.
            {provider === 'linux' && ' Linux: imágenes CirrOS o Ubuntu.'}
            {provider === 'auto' && ' Automático: se planifica en Linux y en OpenStack y se despliega donde ocupe menos servidores nuevos.'}
          </p>
          {needsGuest && (
            <fieldset className="panel-inner">
              <legend>Acceso a las VMs Ubuntu</legend>
              <p className="muted small">Se crea este usuario en cada VM Ubuntu (consola VNC y SSH). La contraseña no se
                guarda: a las plataformas solo llega su hash. La llave SSH es opcional; sin ella se permite SSH con contraseña.</p>
              <div className="upload-grid">
                <label>Usuario
                  <input value={guestUser} autoComplete="off" onChange={(e) => { setGuestUser(e.target.value.trim()); setError('') }} />
                </label>
                <label>Contraseña
                  <input type="password" value={guestPassword} autoComplete="new-password"
                    onChange={(e) => { setGuestPassword(e.target.value); setError('') }} />
                </label>
                <label>Repetir contraseña
                  <input type="password" value={guestConfirm} autoComplete="new-password"
                    onChange={(e) => { setGuestConfirm(e.target.value); setError('') }} />
                </label>
              </div>
              <label>Llaves SSH públicas (opcional, una por línea)
                <textarea rows={2} className="mono small" value={guestKey} placeholder="ssh-ed25519 AAAA… usuario@pc"
                  onChange={(e) => setGuestKey(e.target.value)} />
              </label>
            </fieldset>
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
                      <td>{vm.name}{vm.internet ? ' · Internet' : ''}{vm.host ? ' · ' + vm.host : ''}</td><td>{vm.image}</td><td>{vm.vcpus}</td>
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
