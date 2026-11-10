// Cliente del gateway. Toda llamada va a /api (nginx o Vite la reenvían al gateway).
import { clearSession, getToken } from './session.js'

const MESSAGES = {
  invalid_credentials: 'Usuario o contraseña incorrectos, o la sesión expiró.',
  not_authorized: 'No tienes permiso para esta acción.',
  not_found: 'No existe o no tienes acceso.',
  platform_unavailable: 'El motor de despliegue no está disponible.',
  platform_timeout: 'El motor de despliegue tardó demasiado en responder.',
  slice_manager_unavailable: 'El Slice Manager no está disponible.',
  slice_manager_timeout: 'El Slice Manager tardó demasiado en responder.',
  iam_unavailable: 'El servicio de identidad no está disponible.',
  too_many_attempts: 'Demasiados intentos. Espera un minuto.',
  conflict: 'Conflicto con el estado actual.',
}

export class ApiError extends Error {
  constructor(status, detail) {
    const text = typeof detail === 'string' ? detail : null
    const known = text && MESSAGES[text]
    const spec = text && text.startsWith('invalid_spec: ') ? 'Especificación inválida: ' + text.slice(14) : null
    super(known || spec || text || `Error HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

function newKey() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID().replaceAll('-', '')
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('')
}

export async function api(path, { method = 'GET', body, idempotent = false, auth = true } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = getToken()
    if (token) headers.Authorization = 'Bearer ' + token
  }
  if (idempotent) headers['Idempotency-Key'] = newKey()
  let response
  try {
    response = await fetch('/api' + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError(0, 'No se pudo contactar al gateway.')
  }
  let data = null
  try {
    data = await response.json()
  } catch {
    /* respuesta sin cuerpo JSON */
  }
  if (!response.ok) {
    if (response.status === 401 && auth) clearSession()
    const detail = Array.isArray(data?.detail) ? 'Datos inválidos en el formulario.' : data?.detail
    throw new ApiError(response.status, detail)
  }
  return data
}

export const Api = {
  login: (username, password) => api('/v1/auth/login', { method: 'POST', body: { username, password }, auth: false }),
  me: () => api('/v1/auth/me'),
  logout: () => api('/v1/auth/logout', { method: 'POST' }),
  courses: () => api('/v1/iam/courses'),
  capabilities: () => api('/v1/platform/capabilities'),
  slices: () => api('/v1/slices'),
  slice: (id) => api('/v1/slices/' + id),
  createSlice: (courseId, spec) => api('/v1/slices', { method: 'POST', body: { course_id: courseId, spec }, idempotent: true }),
  deleteSlice: (id) => api('/v1/slices/' + id, { method: 'DELETE', idempotent: true }),
  console: (id, vm) => api(`/v1/slices/${id}/vms/${vm}/console`, { method: 'POST' }),
  assignments: (id) => api(`/v1/slices/${id}/assignments`),
  assign: (id, userId) => api(`/v1/slices/${id}/assignments`, { method: 'POST', body: { user_id: userId } }),
  unassign: (id, userId) => api(`/v1/slices/${id}/assignments/${userId}`, { method: 'DELETE' }),
  students: (courseId) => api(`/v1/iam/courses/${courseId}/students`),
  images: () => api('/v1/images'),
  // Topology Manager (paso 6)
  catalog: () => api('/v1/topologies/catalog'),
  generate: (kind, n, extra = {}) => api('/v1/topologies/generate', { method: 'POST', body: { kind, n, ...extra } }),
  combine: (base, add, connect) => api('/v1/topologies/combine', { method: 'POST', body: connect ? { base, add, connect } : { base, add } }),
  validateTopology: (topology) => api('/v1/topologies/validate', { method: 'POST', body: { topology } }),
  compile: (topology, provider, name) => api('/v1/topologies/compile', { method: 'POST', body: { topology, provider, name } }),
  drafts: () => api('/v1/drafts'),
  draft: (id) => api('/v1/drafts/' + id),
  createDraft: (topology) => api('/v1/drafts', { method: 'POST', body: { topology } }),
  updateDraft: (id, topology, version) => api('/v1/drafts/' + id, { method: 'PUT', body: { topology, version } }),
  deleteDraft: (id) => api('/v1/drafts/' + id, { method: 'DELETE' }),
}

// Importar imagen (D-15): XMLHttpRequest para informar el progreso de la subida.
export function uploadImage(file, { name, disk_format, description }, onProgress) {
  return new Promise((resolve, reject) => {
    const query = new URLSearchParams({ name, disk_format, description: description || '' })
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/v1/images?' + query.toString())
    const token = getToken()
    if (token) xhr.setRequestHeader('Authorization', 'Bearer ' + token)
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100)) }
    xhr.onerror = () => reject(new ApiError(0, 'Se cortó la conexión durante la subida.'))
    xhr.onload = () => {
      let data = null
      try { data = JSON.parse(xhr.responseText) } catch { /* sin JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data)
      if (xhr.status === 401) clearSession()
      const detail = xhr.status === 413 && !data ? 'La imagen supera el tamaño permitido.' : data?.detail
      reject(new ApiError(xhr.status, Array.isArray(detail) ? 'Datos inválidos.' : detail))
    }
    xhr.send(file)
  })
}
