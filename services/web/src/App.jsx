import { useEffect, useState } from 'react'
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { Api } from './api.js'
import { clearSession, getSession, onSessionChange } from './session.js'
import Login from './pages/Login.jsx'
import Slices from './pages/Slices.jsx'
import SliceDetail from './pages/SliceDetail.jsx'
import NewSlice from './pages/NewSlice.jsx'
import Topologies from './pages/Topologies.jsx'
import TopologyEditor from './pages/TopologyEditor.jsx'
import Images from './pages/Images.jsx'
import { canCreate } from './components.jsx'

const ROLE_LABEL = { admin: 'Administrador', professor: 'Profesor', student: 'Alumno' }

function Shell({ user, children }) {
  const navigate = useNavigate()
  async function logout() {
    try {
      await Api.logout()
    } catch {
      /* la sesión puede haber expirado: se cierra igual en el navegador */
    }
    clearSession()
    navigate('/login')
  }
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <img src="/favicon.svg" alt="" width="28" height="28" />
          <div>
            <strong>G5 Cloud Orchestrator</strong>
            <span>PUCP · TEL141</span>
          </div>
        </div>
        <nav>
          <NavLink to="/slices">{user.role === 'admin' ? 'Todos los slices' : 'Mis slices'}</NavLink>
          {canCreate(user) && <NavLink to="/slices/nuevo">Nuevo slice</NavLink>}
          {canCreate(user) && <NavLink to="/topologias">Topologías</NavLink>}
          <NavLink to="/imagenes">Imágenes</NavLink>
        </nav>
        <div className="who">
          <span className={'role role-' + user.role}>{ROLE_LABEL[user.role]}</span>
          <span className="username">{user.username}</span>
          <button className="ghost" onClick={logout}>Cerrar sesión</button>
        </div>
      </header>
      <main>{children}</main>
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState(getSession())
  useEffect(() => onSessionChange(setSession), [])
  // Expiración del token: se cierra la sesión local al vencer.
  useEffect(() => {
    if (!session) return undefined
    const timer = setTimeout(clearSession, Math.max(0, session.expiresAt - Date.now()))
    return () => clearTimeout(timer)
  }, [session])

  // Durante el login hay un instante con token pero sin usuario: se sigue mostrando el login.
  if (!session || !session.user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    )
  }
  const user = session.user
  return (
    <Shell user={user}>
      <Routes>
        <Route path="/slices" element={<Slices user={user} />} />
        <Route path="/slices/nuevo" element={canCreate(user) ? <NewSlice /> : <Navigate to="/slices" replace />} />
        <Route path="/slices/:id" element={<SliceDetail user={user} />} />
        <Route path="/imagenes" element={<Images user={user} />} />
        <Route path="/topologias" element={canCreate(user) ? <Topologies /> : <Navigate to="/slices" replace />} />
        <Route path="/topologias/nueva" element={canCreate(user) ? <TopologyEditor key="nueva" /> : <Navigate to="/slices" replace />} />
        <Route path="/topologias/:id" element={canCreate(user) ? <TopologyEditor /> : <Navigate to="/slices" replace />} />
        <Route path="*" element={<Navigate to="/slices" replace />} />
      </Routes>
    </Shell>
  )
}
