import { Background, ConnectionMode, Controls, Handle, MiniMap, Position, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

function Ports({ isConnectable }) {
  const positions = isConnectable ? [Position.Top, Position.Bottom]
    : [Position.Top, Position.Bottom, Position.Left, Position.Right]
  return positions.map((position) => (
    <Handle key={position} id={isConnectable ? undefined : position} type="source" position={position}
            isConnectable={isConnectable} isConnectableStart={isConnectable} isConnectableEnd={isConnectable} />
  ))
}

function VmNode({ id, data, selected, isConnectable }) {
  const details = [
    data.image,
    data.vcpus != null && `${data.vcpus}\u00a0vCPU`,
    data.memory_mb != null && `${data.memory_mb}\u00a0MB`,
    data.disk_gb != null && `${data.disk_gb}\u00a0GB`,
    data.internet && 'Internet',
    data.host,
  ].filter(Boolean)
  return (
    <div className={'vm-node' + (selected ? ' selected' : '')}>
      <Ports isConnectable={isConnectable} />
      <div className="vm-icon" aria-hidden="true">▣</div>
      <div className="vm-name">{id}</div>
      <div className="vm-meta">{details.join(' · ')}</div>
    </div>
  )
}

function BusNode({ id, data, selected, isConnectable }) {
  return (
    <div className={'bus-node' + (selected ? ' selected' : '')}>
      <Ports isConnectable={isConnectable} />
      <span>bus · {data.label || id}</span>
    </div>
  )
}

const NODE_TYPES = { vm: VmNode, bus: BusNode }

export function TopologyCanvas(props) {
  return (
    <ReactFlow nodeTypes={NODE_TYPES} connectionMode={ConnectionMode.Loose}
               fitView proOptions={{ hideAttribution: true }} {...props}>
      <Background gap={20} />
      <MiniMap pannable zoomable />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}

export function TopologyViewer({ nodes, edges }) {
  // React Flow ajusta el encuadre inicial al montar. Conservar el zoom durante el sondeo del detalle.
  const layout = JSON.stringify(nodes.map(({ id, position }) => [id, position.x, position.y]))
  const positions = new Map(nodes.map((node) => [node.id, node.position]))
  const links = edges.map((edge) => {
    const from = positions.get(edge.source)
    const to = positions.get(edge.target)
    const dx = to.x - from.x
    const dy = to.y - from.y
    const horizontal = Math.abs(dx) > 1.7 * Math.abs(dy)
    const [sourceHandle, targetHandle] = horizontal
      ? (dx > 0 ? [Position.Right, Position.Left] : [Position.Left, Position.Right])
      : (dy > 0 ? [Position.Bottom, Position.Top] : [Position.Top, Position.Bottom])
    return { ...edge, sourceHandle, targetHandle }
  })
  return (
    <div className="canvas topology-viewer" role="region" aria-label="Topología del slice">
      <TopologyCanvas key={layout} nodes={nodes} edges={links} minZoom={0.05}
                      fitViewOptions={{ padding: 0.2, maxZoom: 1.25 }}
                      nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
                      edgesReconnectable={false} deleteKeyCode={null} />
    </div>
  )
}
