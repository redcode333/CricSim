import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Match from './pages/Match'
import Scorecard from './pages/Scorecard'
import Players from './pages/Players'
import Tournament from './pages/Tournament'
import Stats from './pages/Stats'
import Draft from './pages/Draft'
import { useAuth } from './hooks/useAuth'

function PrivateRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login"      element={<Login />} />
        <Route path="/"           element={<PrivateRoute><Landing /></PrivateRoute>} />
        <Route path="/match"      element={<PrivateRoute><Match /></PrivateRoute>} />
        <Route path="/scorecard"  element={<PrivateRoute><Scorecard /></PrivateRoute>} />
        <Route path="/players"    element={<PrivateRoute><Players /></PrivateRoute>} />
        <Route path="/tournament" element={<PrivateRoute><Tournament /></PrivateRoute>} />
        <Route path="/tournament/stats" element={<PrivateRoute><Stats /></PrivateRoute>} />
        <Route path="/draft"      element={<PrivateRoute><Draft /></PrivateRoute>} />
      </Routes>
    </BrowserRouter>
  )
}
