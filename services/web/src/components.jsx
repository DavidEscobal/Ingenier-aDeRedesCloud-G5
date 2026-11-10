import { useEffect, useRef } from 'react'

export const canCreate = (user) => user && (user.role === 'admin' || user.role === 'professor')

export const FINAL = new Set(['READY', 'DELETED', 'FAILED', 'FAILED_CLEANED', 'ERROR'])

const STATUS = {
  QUEUED: ['En cola', 'wait'],
  PENDING: ['En cola', 'wait'],
  DEPLOYING: ['Desplegando', 'busy'],
  READY: ['Listo', 'ok'],
  DELETING: ['Borrando', 'busy'],
  DELETED: ['Borrado', 'off'],
  FAILED: ['Falló', 'bad'],
  FAILED_CLEANED: ['Falló (limpiado)', 'bad'],
  ERROR: ['Error', 'bad'],
}

export function StatusBadge({ status }) {
  const [label, tone] = STATUS[status] || [status || 'Desconocido', 'off']
  return <span className={'badge badge-' + tone}>{label}</span>
}

export function formatDate(seconds) {
  if (!seconds) return '—'
  return new Date(seconds * 1000).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })
}

export function ProviderLabel({ provider }) {
  return <span className={'provider provider-' + provider}>{provider === 'openstack' ? 'OpenStack' : 'Linux'}</span>
}

// Repite `fn` cada `ms` mientras `active` sea verdadero; se detiene al desmontar.
export function usePolling(fn, ms, active) {
  const saved = useRef(fn)
  saved.current = fn
  useEffect(() => {
    if (!active) return undefined
    const timer = setInterval(() => saved.current(), ms)
    return () => clearInterval(timer)
  }, [ms, active])
}

export function ConfirmDialog({ title, children, confirmLabel, busy, onConfirm, onCancel }) {
  return (
    <div className="dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
      <div className="dialog">
        <h3 id="dialog-title">{title}</h3>
        <div className="dialog-body">{children}</div>
        <div className="dialog-actions">
          <button className="ghost" onClick={onCancel} disabled={busy}>Cancelar</button>
          <button className="danger" onClick={onConfirm} disabled={busy}>{busy ? 'Enviando…' : confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}
