import { cn, statusColor } from '@/lib/utils'

interface BadgeProps {
  label: string
  status?: string
  className?: string
}

export function Badge({ label, status, className }: BadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
      status ? statusColor(status) : 'bg-gray-100 text-gray-700',
      className
    )}>
      {label}
    </span>
  )
}
