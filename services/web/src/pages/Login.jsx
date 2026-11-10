import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Api } from '../api.js'
import { clearSession, saveSession } from '../session.js'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  async function submit(event) {
    event.preventDefault()
    if (!username.trim() || !password) {
      setError('Escribe tu usuario y tu contraseña.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const login = await Api.login(username.trim(), password)
      // Se guarda primero el token para poder pedir /me con él; luego se completa la sesión.
      saveSession(login.access_token, login.expires_in, null)
      const me = await Api.me()
      saveSession(login.access_token, login.expires_in, me)
      navigate('/slices')
    } catch (err) {
      clearSession()
      setError(err.message)
    } finally {
      setPassword('')
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={submit} noValidate>
        <div className="brand big">
          <img src="/favicon.svg" alt="" width="40" height="40" />
          <div>
            <strong>G5 Cloud Orchestrator</strong>
            <span>Orquestación de slices sobre Linux y OpenStack</span>
          </div>
        </div>
        <label>
          Usuario
          <input value={username} onChange={(e) => { setUsername(e.target.value); setError('') }}
                 autoComplete="username" autoFocus />
        </label>
        <label>
          Contraseña
          <input type="password" value={password} onChange={(e) => { setPassword(e.target.value); setError('') }}
                 autoComplete="current-password" />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? 'Ingresando…' : 'Ingresar'}</button>
        <p className="hint">La sesión dura 15 minutos y se cierra al cerrar la pestaña.</p>
      </form>
    </div>
  )
}
