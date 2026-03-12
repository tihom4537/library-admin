import { create } from 'zustand'

interface AuthState {
  token: string | null
  role: string | null
  name: string | null
  email: string | null
  setAuth: (token: string, role: string, name: string, email: string) => void
  clear: () => void
}

export const useAuth = create<AuthState>((set) => ({
  token: localStorage.getItem('access_token'),
  role: localStorage.getItem('admin_role'),
  name: localStorage.getItem('admin_name'),
  email: localStorage.getItem('admin_email'),

  setAuth: (token, role, name, email) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('admin_role', role)
    localStorage.setItem('admin_name', name)
    localStorage.setItem('admin_email', email)
    set({ token, role, name, email })
  },

  clear: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('admin_role')
    localStorage.removeItem('admin_name')
    localStorage.removeItem('admin_email')
    set({ token: null, role: null, name: null, email: null })
  },
}))
