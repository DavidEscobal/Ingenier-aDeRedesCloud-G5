// Sesión en sessionStorage: se borra al cerrar la pestaña. El token expira en IAM (15 min).
const KEY = 'g5.session'
const listeners = new Set()
let memory = null // respaldo si sessionStorage está bloqueado

function read() {
  let value = memory
  try {
    value = JSON.parse(sessionStorage.getItem(KEY) || 'null') || memory
  } catch {
    /* almacenamiento bloqueado o sesión corrupta: se usa la memoria */
  }
  return value && value.expiresAt > Date.now() ? value : null
}

export function getToken() {
  return read()?.token || null
}

export function getSession() {
  return read()
}

export function saveSession(token, expiresIn, user) {
  const value = { token, user, expiresAt: Date.now() + expiresIn * 1000 }
  memory = value
  try {
    sessionStorage.setItem(KEY, JSON.stringify(value))
  } catch {
    /* almacenamiento bloqueado: la sesión vive solo en memoria de esta vista */
  }
  listeners.forEach((fn) => fn(value))
  return value
}

export function clearSession() {
  memory = null
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    /* sin almacenamiento */
  }
  listeners.forEach((fn) => fn(null))
}

export function onSessionChange(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}
