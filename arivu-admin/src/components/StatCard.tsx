import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: LucideIcon
  color: 'blue' | 'green' | 'orange' | 'purple'
}

const colorMap = {
  blue:   { bg: 'bg-blue-50',   icon: 'text-blue-600',   border: 'border-blue-100' },
  green:  { bg: 'bg-green-50',  icon: 'text-green-600',  border: 'border-green-100' },
  orange: { bg: 'bg-orange-50', icon: 'text-orange-600', border: 'border-orange-100' },
  purple: { bg: 'bg-purple-50', icon: 'text-purple-600', border: 'border-purple-100' },
}

export function StatCard({ title, value, subtitle, icon: Icon, color }: StatCardProps) {
  const c = colorMap[color]
  return (
    <div className={cn('bg-white rounded-xl p-5 border shadow-sm flex items-start gap-4', c.border)}>
      <div className={cn('p-2.5 rounded-lg', c.bg)}>
        <Icon className={cn('w-5 h-5', c.icon)} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-500">{title}</p>
        <p className="text-2xl font-bold text-slate-800 mt-0.5">{value}</p>
        {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
      </div>
    </div>
  )
}
