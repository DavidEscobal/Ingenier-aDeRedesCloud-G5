import assert from 'node:assert/strict'
import test from 'node:test'
import { sliceToFlow, toFlow } from '../src/topology.js'

test('el detalle conserva las VMs aisladas, recursos y enlaces compartidos por dos VMs', () => {
  const { nodes, edges } = sliceToFlow([
    { name: 'n1', host: 'worker1', disk_gb: 2.5, networks: ['a', 'a'] },
    { name: 'n2', networks: ['a', 'b'] }, { name: 'n3', networks: ['b'] }, { name: 'aislada' },
  ])
  assert.equal(nodes.length, 4)
  assert.equal(nodes[0].data.host, 'worker1')
  assert.equal(nodes[0].data.disk_gb, 2.5)
  assert.deepEqual(edges.map(({ source, target }) => [source, target]), [['n1', 'n2'], ['n2', 'n3']])
})

test('una red de uno o varios miembros tiene identidad propia aunque coincida con una VM', () => {
  const { nodes, edges } = sliceToFlow([
    { name: 'n1', networks: ['n1', 'solo'] }, { name: 'n2', networks: ['n1'] }, { name: 'n3', networks: ['n1'] },
  ])
  assert.deepEqual(nodes.filter((n) => n.type === 'bus').map((n) => n.data.label), ['n1', 'solo'])
  assert.equal(new Set(nodes.map((n) => n.id)).size, nodes.length)
  assert.deepEqual(edges.map((e) => e.target), ['net:n1', 'net:n1', 'net:n1', 'net:solo'])
})

test('dos VMs conectadas por dos redes conservan ambos caminos', () => {
  const { nodes, edges } = sliceToFlow(['a', 'b'].map((name) => ({ name, networks: ['x', 'y'] })))
  assert.equal(nodes.length, 3)
  assert.deepEqual(edges.map((e) => [e.source, e.target]), [['a', 'b'], ['a', 'net:y'], ['b', 'net:y']])
})

test('la vista previa conserva posiciones, bus de dos miembros y enlace sin IP del editor', () => {
  const position = { x: 0, y: 100 }
  const { nodes, edges } = toFlow({
    nodes: [{ id: 'a', position }, { id: 'b' }],
    segments: [{ id: 'lan', kind: 'bus', members: ['a', 'b'], position },
      { id: 'l2', kind: 'link', members: ['a', 'b'], addressed: false }],
  })
  assert.deepEqual(nodes[0].position, position)
  assert.deepEqual(nodes[2].position, position)
  assert.equal(nodes[2].type, 'bus')
  assert.ok(edges.find((e) => e.id === 'l2').style.strokeDasharray)
})
