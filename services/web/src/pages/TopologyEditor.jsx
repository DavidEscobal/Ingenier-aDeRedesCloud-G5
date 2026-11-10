import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Background, ConnectionMode, Controls, Handle, MiniMap, Position, ReactFlow, useEdgesState, useNodesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Api } from '../api.js'
import { download, freeId, fromFlow, IDENT, localProblems, toFlow } from '../topology.js'

function sizeOf(data, sizes) {
  return sizes.find((s) => s.vcpus === data.vcpus && s.memory_mb === data.memory_mb && s.disk_gb === data.disk_gb)
}

function VmNode({ id, data, selected }) {
  return (
    <div className={'vm-node' + (selected ? ' selected' : '')}>
      <Handle type="source" position={Position.Top} />
      <div className="vm-icon" aria-hidden="true">▣</div>
      <div className="vm-name">{id}</div>
      <div className="vm-meta">{data.image} · {data.vcpus} vCPU · {data.memory_mb} MB · {data.disk_gb} GB</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

function BusNode({ id, selected }) {
  return (
    <div className={'bus-node' + (selected ? ' selected' : '')}>
      <Handle type="source" position={Position.Top} />
      <span>bus · {id}</span>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const NODE_TYPES = { vm: VmNode, bus: BusNode }
const PREFIXES = ['n', 'a', 'b', 'c', 'd', 'e', 'f', 'g']

export default function TopologyEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [name, setName] = useState('mi-topologia')
  const [description, setDescription] = useState('')
  const [draft, setDraft] = useState(null) // {id, version}
  const [catalog, setCatalog] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [generator, setGenerator] = useState(null) // {kind, n}
  const [deploy, setDeploy] = useState(null) // {courses, course, sliceName}
  const [renameValue, setRenameValue] = useState('')

  const [imageNames, setImageNames] = useState(null)
  useEffect(() => {
    Api.catalog().then(setCatalog).catch((err) => setError(err.message))
    // Imágenes reales del catálogo (D-15); si no responde, se usa la lista base del Topology Manager.
    Api.images().then((list) => setImageNames(list.map((i) => i.name))).catch(() => setImageNames(null))
  }, [])

  useEffect(() => {
    if (!id) return
    Api.draft(id)
      .then((d) => {
        const flow = toFlow(d.topology)
        setNodes(flow.nodes)
        setEdges(flow.edges)
        setName(d.topology.name)
        setDescription(d.topology.description || '')
        setDraft({ id: d.id, version: d.version })
        setDirty(false)
      })
      .catch((err) => setError(err.message))
  }, [id, setNodes, setEdges])

  const sizes = catalog?.sizes || []
  const selectedNode = nodes.find((n) => n.selected)
  const selectedEdge = edges.find((e) => e.selected)
  useEffect(() => { setRenameValue(selectedNode?.id || '') }, [selectedNode?.id])

  const topology = useMemo(() => fromFlow(nodes, edges, name, description), [nodes, edges, name, description])
  const problems = useMemo(() => localProblems(topology), [topology])
  const changed = () => { setDirty(true); setNotice('') }

  const usedIds = () => new Set([...nodes.map((n) => n.id), ...edges.map((e) => e.data?.segment).filter(Boolean)])

  const onConnect = useCallback((conn) => {
    const { source, target } = conn
    if (!source || !target || source === target) return
    const kind = (nid) => nodes.find((n) => n.id === nid)?.type
    if (kind(source) === 'bus' && kind(target) === 'bus') return setError('No se pueden unir dos buses entre sí.')
    if (kind(source) === 'bus' || kind(target) === 'bus') {
      const bus = kind(source) === 'bus' ? source : target
      const vm = bus === source ? target : source
      if (edges.some((e) => e.id === `${bus}:${vm}`)) return
      setEdges((es) => [...es, { id: `${bus}:${vm}`, source: vm, target: bus, type: 'straight', data: { bus } }])
    } else {
      if (edges.some((e) => (e.source === source && e.target === target) || (e.source === target && e.target === source))) {
        return setError(`Ya existe un enlace entre ${source} y ${target}.`)
      }
      const sid = freeId(usedIds(), `${source}-${target}`.slice(0, 32))
      setEdges((es) => [...es, { id: sid, source, target, type: 'straight', data: { segment: sid } }])
    }
    setError('')
    changed()
  }, [nodes, edges, setEdges]) // eslint-disable-line react-hooks/exhaustive-deps

  function addVm() {
    const used = usedIds()
    let k = nodes.filter((n) => n.type === 'vm').length + 1
    while (used.has(`vm${k}`)) k += 1
    const s = sizes[0] || { vcpus: 1, memory_mb: 512, disk_gb: 1 }
    setNodes((ns) => [...ns.map((n) => ({ ...n, selected: false })), {
      id: `vm${k}`, type: 'vm', selected: true, position: { x: 120 + (k % 5) * 60, y: 120 + (k % 4) * 50 },
      data: { image: catalog?.images?.[0] || 'cirros', vcpus: s.vcpus, memory_mb: s.memory_mb, disk_gb: s.disk_gb },
    }])
    changed()
  }

  function addBus() {
    const bid = freeId(usedIds(), 'bus')
    setNodes((ns) => [...ns, { id: bid, type: 'bus', position: { x: 300, y: 40 }, data: {} }])
    setNotice(`Bus ${bid} agregado: conecta al menos 2 VMs a él.`)
    setDirty(true)
  }

  async function applyGenerator(mode) {
    const { kind, n } = generator
    setBusy(true)
    setError('')
    try {
      const current = fromFlow(nodes, edges, name, description)
      const empty = current.nodes.length === 0
      const prefix = mode === 'replace' || empty ? 'n'
        : PREFIXES.find((p) => !current.nodes.some((x) => x.id === `${p}1`)) || 'x'
      const generated = await Api.generate(kind, n, { prefix, size: sizes[0]?.id || 'small' })
      const result = mode === 'replace' || empty ? generated : await Api.combine(current, generated)
      const flow = toFlow(result)
      setNodes(flow.nodes)
      setEdges(flow.edges)
      if (mode === 'replace' || empty) setName(generated.name)
      setGenerator(null)
      changed()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function updateSelected(patch) {
    setNodes((ns) => ns.map((n) => (n.id === selectedNode.id ? { ...n, data: { ...n.data, ...patch } } : n)))
    changed()
  }

  function renameSelected() {
    const old = selectedNode.id
    const value = renameValue.trim()
    if (value === old) return
    if (!IDENT.test(value)) return setError('Nombre: empieza con letra; minúsculas, números y guiones (máx. 32).')
    if (usedIds().has(value)) return setError(`Ya existe un elemento llamado ${value}.`)
    setNodes((ns) => ns.map((n) => (n.id === old ? { ...n, id: value } : n)))
    setEdges((es) => es.map((e) => {
      const next = { ...e, source: e.source === old ? value : e.source, target: e.target === old ? value : e.target }
      if (e.data?.bus === old) next.data = { bus: value }
      if (e.data?.bus) next.id = `${next.data.bus}:${next.source}`
      return next
    }))
    setError('')
    changed()
  }

  function deleteSelection() {
    const removeNodes = new Set(nodes.filter((n) => n.selected).map((n) => n.id))
    setNodes((ns) => ns.filter((n) => !removeNodes.has(n.id)))
    setEdges((es) => es.filter((e) => !e.selected && !removeNodes.has(e.source) && !removeNodes.has(e.target)))
    changed()
  }

  async function save() {
    const blocking = problems.filter((p) => !p.startsWith('VMs sin conexión'))
    if (blocking.length) return setError(blocking.join(' '))
    setBusy(true)
    setError('')
    try {
      const saved = draft ? await Api.updateDraft(draft.id, topology, draft.version) : await Api.createDraft(topology)
      setDraft({ id: saved.id, version: saved.version })
      setDirty(false)
      setNotice(`Guardada como versión ${saved.version}.`)
      if (!draft) navigate('/topologias/' + saved.id, { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function openDeploy() {
    if (problems.length) return setError(problems.join(' '))
    setError('')
    try {
      const courses = await Api.courses()
      setDeploy({ courses, course: courses[0]?.id || '', sliceName: name })
    } catch (err) {
      setError(err.message)
    }
  }

  async function confirmDeploy() {
    if (!IDENT.test(deploy.sliceName)) return setError('Nombre del slice inválido.')
    setBusy(true)
    setError('')
    try {
      const spec = await Api.compile(topology, 'openstack', deploy.sliceName)
      const accepted = await Api.createSlice(deploy.course, spec)
      navigate('/slices/' + accepted.slice_id)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  const vmCount = topology.nodes.length
  const totals = topology.nodes.reduce((a, n) => ({ cpu: a.cpu + n.vcpus, ram: a.ram + n.memory_mb, disk: a.disk + n.disk_gb }),
    { cpu: 0, ram: 0, disk: 0 })

  return (
    <section className="editor-page">
      <Link to="/topologias" className="back">← Topologías</Link>
      <div className="page-head">
        <div>
          <h1>{draft ? 'Editar topología' : 'Nueva topología'} {dirty && <span className="badge badge-wait">Sin guardar</span>}</h1>
          <p className="sub">{vmCount} VMs · {topology.segments.length} segmentos · {totals.cpu} vCPU · {totals.ram} MB · {totals.disk} GB
            {draft && <> · versión {draft.version}</>}</p>
        </div>
        <div className="head-actions">
          <button className="ghost" onClick={() => download(topology)} disabled={!vmCount}>Exportar JSON</button>
          <button className="ghost" onClick={save} disabled={busy || !vmCount}>{busy ? 'Guardando…' : 'Guardar'}</button>
          <button onClick={openDeploy} disabled={busy || !vmCount}>Desplegar como slice</button>
        </div>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="notice">{notice}</p>}

      <div className="editor-grid">
        <aside className="panel side">
          <label>Nombre<input value={name} onChange={(e) => { setName(e.target.value.toLowerCase()); changed() }} /></label>
          <label>Descripción<input value={description} maxLength={300} onChange={(e) => { setDescription(e.target.value); changed() }} /></label>
          <h3>Topologías predefinidas</h3>
          <div className="chips">
            {(catalog?.generators || []).map((g) => (
              <button key={g.id} className="chip" onClick={() => setGenerator({ kind: g.id, n: Math.min(Math.max(4, g.min), g.max), ...g })}>{g.label}</button>
            ))}
          </div>
          <h3>Elementos</h3>
          <div className="chips">
            <button className="chip" onClick={addVm} disabled={vmCount >= 16}>+ VM</button>
            <button className="chip" onClick={addBus}>+ Bus</button>
            <button className="chip danger-chip" onClick={deleteSelection} disabled={!selectedNode && !selectedEdge}>Eliminar selección</button>
          </div>
          <p className="hint">Conecta arrastrando desde el punto superior o inferior de una VM hasta otra VM o un bus. Supr/Retroceso borra lo seleccionado.</p>

          {selectedNode && (
            <div className="inspector">
              <h3>{selectedNode.type === 'bus' ? 'Bus' : 'VM'} seleccionado</h3>
              <label>Nombre
                <div className="inline"><input value={renameValue} onChange={(e) => setRenameValue(e.target.value.toLowerCase())} />
                  <button className="ghost" onClick={renameSelected}>Renombrar</button></div>
              </label>
              {selectedNode.type === 'vm' && (
                <>
                  <label>Tamaño
                    <select value={sizeOf(selectedNode.data, sizes)?.id || ''} onChange={(e) => {
                      const s = sizes.find((x) => x.id === e.target.value)
                      updateSelected({ vcpus: s.vcpus, memory_mb: s.memory_mb, disk_gb: s.disk_gb })
                    }}>
                      {!sizeOf(selectedNode.data, sizes) && <option value="">No disponible — elige uno</option>}
                      {sizes.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                    </select>
                  </label>
                  <label>Imagen
                    <select value={selectedNode.data.image} onChange={(e) => updateSelected({ image: e.target.value })}>
                      {[...new Set([...(imageNames || catalog?.images || []), selectedNode.data.image])].map((i) => <option key={i} value={i}>{i}</option>)}
                    </select>
                  </label>
                </>
              )}
            </div>
          )}
          {selectedEdge && !selectedNode && (
            <div className="inspector">
              <h3>Enlace seleccionado</h3>
              <p className="small">{selectedEdge.source} ↔ {selectedEdge.target}</p>
            </div>
          )}
          {problems.length > 0 && vmCount > 0 && (
            <ul className="problems">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
          )}
        </aside>

        <div className="canvas">
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} connectionMode={ConnectionMode.Loose}
                     onNodesChange={(c) => { onNodesChange(c); if (c.some((x) => x.type === 'position' && x.dragging === false || x.type === 'remove')) setDirty(true) }}
                     onEdgesChange={(c) => { onEdgesChange(c); if (c.some((x) => x.type === 'remove')) setDirty(true) }}
                     onConnect={onConnect} fitView deleteKeyCode={['Backspace', 'Delete']} proOptions={{ hideAttribution: true }}>
            <Background gap={20} />
            <MiniMap pannable zoomable />
            <Controls showInteractive={false} />
          </ReactFlow>
          {vmCount === 0 && !nodes.length && (
            <div className="canvas-empty">Elige una topología predefinida o agrega VMs para empezar.</div>
          )}
        </div>
      </div>

      {generator && (
        <div className="dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="gen-title">
          <div className="dialog">
            <h3 id="gen-title">{generator.label}</h3>
            <label>Número de VMs ({generator.min}–{generator.max})
              <input type="number" min={generator.min} max={generator.max} value={generator.n}
                     onChange={(e) => setGenerator({ ...generator, n: Number(e.target.value) })} />
            </label>
            {(generator.n < generator.min || generator.n > generator.max) && <p className="error">Debe estar entre {generator.min} y {generator.max}.</p>}
            <div className="dialog-actions">
              <button className="ghost" onClick={() => setGenerator(null)} disabled={busy}>Cancelar</button>
              {vmCount > 0 && <button className="ghost" onClick={() => applyGenerator('add')}
                disabled={busy || generator.n < generator.min || generator.n > generator.max}>Combinar con lo actual</button>}
              <button onClick={() => applyGenerator('replace')}
                      disabled={busy || generator.n < generator.min || generator.n > generator.max}>{vmCount > 0 ? 'Reemplazar' : 'Crear'}</button>
            </div>
          </div>
        </div>
      )}

      {deploy && (
        <div className="dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="dep-title">
          <div className="dialog">
            <h3 id="dep-title">Desplegar «{name}»</h3>
            <label>Curso
              <select value={deploy.course} onChange={(e) => setDeploy({ ...deploy, course: e.target.value })}>
                {deploy.courses.length === 0 && <option value="">No estás matriculado en ningún curso</option>}
                {deploy.courses.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.name}</option>)}
              </select>
            </label>
            <label>Nombre del slice
              <input value={deploy.sliceName} onChange={(e) => setDeploy({ ...deploy, sliceName: e.target.value.toLowerCase() })} />
            </label>
            <p className="small muted">Proveedor: OpenStack · {vmCount} VMs · {topology.segments.length} redes (10.60.k.0/24)</p>
            {error && <p className="error">{error}</p>}
            <div className="dialog-actions">
              <button className="ghost" onClick={() => { setDeploy(null); setError('') }} disabled={busy}>Cancelar</button>
              <button onClick={confirmDeploy} disabled={busy || !deploy.course}>{busy ? 'Desplegando…' : 'Desplegar'}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
