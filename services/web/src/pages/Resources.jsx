// Recursos del sistema (R1B-I-12, R4-I-01): servidores Linux y OpenStack según el servicio de monitoreo.
import { useCallback, useEffect, useState } from 'react'
import { Api } from '../api.js'

const PROVIDER = { linux: 'Clúster Linux', openstack: 'OpenStack' }

function pct(used, total) {
  return total ? Math.min(100, Math.round((100 * used) / total)) : 0
}

function Meter({ used, total, unit = '', limit }) {
  const p = pct(used, total)
  const level = p >= 90 ? 'bad' : p >= (limit || 75) ? 'wait' : 'ok'
  return (
    <div className="meter" title={`${used} / ${total} ${unit} (${p} %)`}>
      <div className="meter-track"><div className={'meter-fill meter-' + level} style={{ width: p + '%' }} /></div>
      <span className="small">{used} / {total} {unit}</span>
    </div>
  )
}

function gb(mb) {
  return mb == null ? '—' : (mb / 1024).toFixed(mb < 10240 ? 1 : 0)
}

function Health({ host }) {
  if (host.healthy) return <span className="badge badge-ok">Disponible</span>
  return <span className="badge badge-bad" title={host.error || ''}>{host.error ? 'No disponible' : 'Sin datos'}</span>
}

function Sparkline({ points }) {
  const values = points.map((p) => p.cpu_real_cent ?? 0)
  const max = Math.max(100, ...values)
  const w = 520, h = 90
  const xy = values.map((v, i) => `${(i / Math.max(1, values.length - 1)) * w},${h - (v / max) * (h - 8) - 4}`)
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="CPU real en el tiempo">
      <polyline points={xy.join(' ')} fill="none" stroke="var(--accent)" strokeWidth="2" />
    </svg>
  )
}

function History({ host, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    Api.monitoringHistory(host.id, 60).then(setData).catch((e) => setError(e.message))
  }, [host.id])
  const last = data?.points?.[data.points.length - 1]
  return (
    <div className="panel" style={{ marginTop: 16 }}>
      <div className="page-head" style={{ marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>{host.id} · última hora</h3>
        <button className="ghost" onClick={onClose}>Cerrar</button>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="muted">Cargando…</p>}
      {data && (
        <>
          <p className="muted small">
            CPU real (centésimas de CPU), {data.points.length} muestras.
            {last && host.provider === 'openstack' && ' En OpenStack no hay CPU real (sin acceso a los workers): se usa la demanda completa.'}
          </p>
          <Sparkline points={data.points} />
        </>
      )}
      {host.vm_usage?.length > 0 && (
        <table className="table compact" style={{ marginTop: 12 }}>
          <thead><tr><th>Slice</th><th>VM</th><th>CPU real</th><th>RAM residente</th></tr></thead>
          <tbody>
            {host.vm_usage.map((v) => (
              <tr key={v.pid}>
                <td className="mono small">{v.sid.slice(0, 8)}</td><td>{v.vm}</td>
                <td>{(v.cpu_cent / 100).toFixed(2)} CPU</td><td>{v.rss_mb} MB</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function Resources() {
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)

  const load = useCallback(async () => {
    try {
      setState(await Api.monitoringState())
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [])
  useEffect(() => {
    load()
    const timer = setInterval(load, 10000)
    return () => clearInterval(timer)
  }, [load])

  const groups = ['linux', 'openstack'].map((p) => [p, (state?.hosts || []).filter((h) => h.provider === p)])

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Recursos</h1>
          <p className="sub">
            Servidores disponibles y su consumo. Lo comprometido sale de las reservas de G5 (Linux) y de Nova
            (OpenStack); la CPU real, del monitoreo. Se actualiza cada 10 s.
          </p>
        </div>
        {state && <span className="muted small">Muestra de hace {Math.round(state.age_s)} s</span>}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {state?.collector_error && <p className="error">Monitoreo: {state.collector_error}</p>}
      {!state && !error && <p className="muted">Cargando…</p>}

      {state && groups.map(([provider, hosts]) => (
        <div key={provider} style={{ marginBottom: 24 }}>
          <h2>{PROVIDER[provider]}</h2>
          {provider === 'openstack' && state.openstack_error && <p className="error">OpenStack: {state.openstack_error}</p>}
          {hosts.length === 0 ? <p className="muted">Sin servidores reportados.</p> : (
            <table className="table">
              <thead>
                <tr>
                  <th>Servidor</th><th>Zona</th><th>Estado</th><th>vCPU comprometidas</th><th>CPU real</th>
                  <th>RAM (MB)</th><th>Disco (GB)</th><th>VMs</th><th>Dato</th><th></th>
                </tr>
              </thead>
              <tbody>
                {hosts.map((h) => {
                  const vcpuCap = h.vcpus_max ?? h.cpu_cores * 2
                  return (
                    <tr key={h.id}>
                      <td><strong>{h.id}</strong><div className="muted small">{h.cpu_cores} CPU</div></td>
                      <td>{h.zone}</td>
                      <td><Health host={h} /></td>
                      <td><Meter used={h.vcpus_used} total={vcpuCap} /></td>
                      <td>{h.cpu_real_cent == null ? <span className="muted small">sin dato</span>
                        : <Meter used={(h.cpu_real_cent / 100).toFixed(1)} total={h.cpu_cores} unit="CPU" limit={85} />}</td>
                      <td><Meter used={h.ram_used_mb} total={h.ram_mb} /></td>
                      <td><Meter used={gb(h.disk_used_mb)} total={gb(h.disk_mb)} /></td>
                      <td>{h.vms}</td>
                      <td className="small">{h.age_s == null ? '—' : Math.round(h.age_s) + ' s'}</td>
                      <td className="actions"><button className="link" onClick={() => setSelected(h)}>Historial</button></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      ))}
      {selected && <History host={selected} onClose={() => setSelected(null)} />}
    </section>
  )
}
