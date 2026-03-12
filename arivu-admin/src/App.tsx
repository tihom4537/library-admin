import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import { Librarians } from '@/pages/Librarians'
import { LibrarianDetail } from '@/pages/LibrarianDetail'
import { Activities } from '@/pages/Activities'
import { Circulars } from '@/pages/Circulars'
import { Nudges } from '@/pages/Nudges'
import { Community } from '@/pages/Community'
import { Learning } from '@/pages/Learning'
import { Export } from '@/pages/Export'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/librarians" element={<Librarians />} />
          <Route path="/librarians/:id" element={<LibrarianDetail />} />
          <Route path="/activities" element={<Activities />} />
          <Route path="/circulars" element={<Circulars />} />
          <Route path="/nudges" element={<Nudges />} />
          <Route path="/community" element={<Community />} />
          <Route path="/learning" element={<Learning />} />
          <Route path="/export" element={<Export />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
