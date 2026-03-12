import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, Activity, BookOpen,
  FileText, LogOut, ChevronRight, Bell, ImageIcon,
  GraduationCap, Download
} from 'lucide-react'
import { useAuth } from '@/store/auth'
import { cn } from '@/lib/utils'

const links = [
  { to: '/',            icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/librarians',  icon: Users,           label: 'Librarians' },
  { to: '/activities',  icon: Activity,        label: 'Activities' },
  { to: '/circulars',   icon: FileText,        label: 'Circulars' },
  { to: '/nudges',      icon: Bell,            label: 'Nudges' },
  { to: '/community',   icon: ImageIcon,       label: 'Community' },
  { to: '/learning',    icon: GraduationCap,   label: 'Learning' },
  { to: '/export',      icon: Download,        label: 'Export' },
]

export function Sidebar() {
  const { name, role, clear } = useAuth()
  const navigate = useNavigate()

  const logout = () => { clear(); navigate('/login') }

  return (
    <aside className="w-60 min-h-screen bg-slate-900 text-white flex flex-col shrink-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <BookOpen className="w-6 h-6 text-blue-400" />
          <span className="text-lg font-bold tracking-tight">Arivu Admin</span>
        </div>
        <p className="text-xs text-slate-400 mt-1 capitalize">{role?.replace('_', ' ')}</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => cn(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
              isActive
                ? 'bg-blue-600 text-white'
                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
            {to !== '/' && <ChevronRight className="w-3 h-3 ml-auto opacity-40" />}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-4 py-4 border-t border-slate-700">
        <p className="text-sm font-medium text-white truncate">{name}</p>
        <button
          onClick={logout}
          className="mt-2 flex items-center gap-2 text-xs text-slate-400 hover:text-red-400 transition-colors"
        >
          <LogOut className="w-3 h-3" /> Sign out
        </button>
      </div>
    </aside>
  )
}
