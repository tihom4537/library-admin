export function cn(...classes: (string | undefined | null | false)[]) {
  return classes.filter(Boolean).join(' ')
}

export function fmtDate(d: string | null | undefined) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function fmtDateTime(d: string | null | undefined) {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function statusColor(status: string) {
  const map: Record<string, string> = {
    onboarded: 'bg-green-100 text-green-800',
    active:    'bg-green-100 text-green-800',
    inactive:  'bg-yellow-100 text-yellow-800',
    pending:   'bg-gray-100 text-gray-600',
    never_onboarded: 'bg-gray-100 text-gray-500',
    published: 'bg-blue-100 text-blue-800',
    draft:     'bg-gray-100 text-gray-600',
    archived:  'bg-red-100 text-red-700',
    sent:      'bg-purple-100 text-purple-800',
    approved:  'bg-green-100 text-green-800',
    open:      'bg-orange-100 text-orange-800',
    resolved:  'bg-green-100 text-green-800',
  }
  return map[status] ?? 'bg-gray-100 text-gray-600'
}
