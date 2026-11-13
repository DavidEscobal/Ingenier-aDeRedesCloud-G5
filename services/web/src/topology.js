// Conversión entre el documento del Topology Manager (schema_version 1) y el lienzo de React Flow.
// - VM  → nodo tipo 'vm'.
// - Segmento 'link' (2 VMs) → arista directa VM–VM.
// - Segmento 'bus' (N VMs)   → nodo tipo 'bus' + una arista por VM miembro.

export const IDENT = /^[a-z][a-z0-9-]{0,31}$/

export function toFlow(topology) {
  const nodes = topology.nodes.map((n, i) => ({
    id: n.id,
    type: 'vm',
    position: n.position || { x: 80 + (i % 6) * 170, y: 80 + Math.floor(i / 6) * 150 },
    data: { image: n.image, vcpus: n.vcpus, memory_mb: n.memory_mb, disk_gb: n.disk_gb, internet: !!n.internet },
  }))
  const edges = []
  for (const s of topology.segments || []) {
    if (s.kind === 'link') {
      edges.push({ id: s.id, source: s.members[0], target: s.members[1], type: 'straight', data: { segment: s.id } })
    } else {
      const xs = s.members.map((m) => nodes.find((n) => n.id === m)?.position.x || 0)
      nodes.push({ id: s.id, type: 'bus', position: s.position || { x: xs.reduce((a, b) => a + b, 0) / xs.length, y: 40 }, data: {} })
      for (const m of s.members) edges.push({ id: `${s.id}:${m}`, source: m, target: s.id, type: 'straight', data: { bus: s.id } })
    }
  }
  return { nodes, edges }
}

export function fromFlow(nodes, edges, name, description = '') {
  const vms = nodes.filter((n) => n.type === 'vm')
  const buses = nodes.filter((n) => n.type === 'bus')
  const isBus = new Set(buses.map((b) => b.id))
  const segments = []
  for (const e of edges) {
    if (isBus.has(e.source) || isBus.has(e.target)) continue
    segments.push({ id: e.data?.segment || e.id, kind: 'link', members: [e.source, e.target] })
  }
  for (const b of buses) {
    const members = edges.filter((e) => e.source === b.id || e.target === b.id)
      .map((e) => (e.source === b.id ? e.target : e.source))
    segments.push({ id: b.id, kind: 'bus', members, position: round(b.position) })
  }
  return {
    schema_version: 1,
    name,
    description,
    nodes: vms.map((n) => ({ id: n.id, image: n.data.image, vcpus: n.data.vcpus, memory_mb: n.data.memory_mb,
      disk_gb: n.data.disk_gb, ...(n.data.internet ? { internet: true } : {}), position: round(n.position) })),
    segments,
  }
}

function round(p) {
  return { x: Math.round(p.x), y: Math.round(p.y) }
}

// Comprobaciones locales rápidas; el Topology Manager vuelve a validar todo al guardar o compilar.
export function localProblems(topology) {
  const problems = []
  if (!IDENT.test(topology.name)) problems.push('Nombre: empieza con letra; minúsculas, números y guiones (máx. 32).')
  if (topology.nodes.length === 0) problems.push('Agrega al menos una VM.')
  if (topology.nodes.length > 16) problems.push('Máximo 16 VMs por topología.')
  for (const s of topology.segments) {
    if (s.kind === 'bus' && s.members.length < 2) problems.push(`El bus ${s.id} necesita al menos 2 VMs conectadas.`)
  }
  const connected = new Set(topology.segments.flatMap((s) => s.members))
  const lonely = topology.nodes.filter((n) => !connected.has(n.id)).map((n) => n.id)
  if (lonely.length) problems.push(`VMs sin conexión (no se pueden desplegar): ${lonely.join(', ')}.`)
  return problems
}

export function freeId(used, base) {
  if (!used.has(base)) return base
  let i = 2
  while (used.has(`${base}-${i}`)) i += 1
  return `${base}-${i}`
}

export function download(topology) {
  const blob = new Blob([JSON.stringify(topology, null, 2) + '\n'], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${topology.name}.topology.json`
  a.click()
  URL.revokeObjectURL(url)
}
