import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, ChevronRight, ChevronLeft } from 'lucide-react'
import api from '@/lib/api'
import { Badge } from '@/components/Badge'
import { fmtDateTime } from '@/lib/utils'

interface LibrarianItem {
  id: string
  name: string
  phone: string
  library_name: string
  district: string | null
  taluk: string | null
  status: string
  last_active_at: string | null
  reports_this_month: number
  activity_status: string
}

interface Response {
  total: number
  page: number
  page_size: number
  items: LibrarianItem[]
}

export function Librarians() {
  const navigate = useNavigate()
  const [data, setData] = useState<Response | null>(null)
  const [search, setSearch] = useState('')
  const [district, setDistrict] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  useEffect(() => { load() }, [search, district, status, page])

  async function load() {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(page), page_size: '20' })
      if (search)   params.set('search', search)
      if (district) params.set('district', district)
      if (status)   params.set('status', status)
      const res = await api.get(`/librarians?${params}`)
      setData(res.data)
    } finally {
      setLoading(false)
    }
  }

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1

  return (
    <div className="p-6 space-y-5">
      <h1 className="text-2xl font-bold text-slate-800">Librarian Directory</h1>

      {/* Filters */}
      <div className="bg-white rounded-xl border shadow-sm p-4 flex flex-wrap gap-3">
        <div className="flex items-center gap-2 border rounded-lg px-3 py-2 flex-1 min-w-52">
          <Search className="w-4 h-4 text-slate-400 shrink-0" />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search name, phone, library…"
            className="text-sm outline-none w-full"
          />
        </div>
        <input
          value={district}
          onChange={e => { setDistrict(e.target.value); setPage(1) }}
          placeholder="District"
          className="border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={status}
          onChange={e => { setStatus(e.target.value); setPage(1) }}
          className="border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All statuses</option>
          <option value="onboarded">Onboarded</option>
          <option value="pending">Pending</option>
          <option value="inactive">Inactive</option>
        </select>
        {data && (
          <span className="text-sm text-slate-500 self-center ml-auto">
            {data.total} librarians
          </span>
        )}
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b">
              <th className="text-left px-4 py-3 font-medium text-slate-600">Name</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Phone</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">District · Taluk</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Status</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Reports/Mo</th>
              <th className="text-left px-4 py-3 font-medium text-slate-600">Last Active</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading && (
              <tr><td colSpan={7} className="text-center py-12 text-slate-400">Loading…</td></tr>
            )}
            {!loading && data?.items.length === 0 && (
              <tr><td colSpan={7} className="text-center py-12 text-slate-400">No librarians found</td></tr>
            )}
            {!loading && data?.items.map(lib => (
              <tr
                key={lib.id}
                onClick={() => navigate(`/librarians/${lib.id}`)}
                className="hover:bg-slate-50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{lib.name}</p>
                  <p className="text-xs text-slate-400">{lib.library_name}</p>
                </td>
                <td className="px-4 py-3 text-slate-600">{lib.phone}</td>
                <td className="px-4 py-3 text-slate-600">
                  {lib.district ?? '—'} {lib.taluk ? `· ${lib.taluk}` : ''}
                </td>
                <td className="px-4 py-3">
                  <Badge label={lib.activity_status.replace(/_/g, ' ')} status={lib.activity_status} />
                </td>
                <td className="px-4 py-3 text-slate-700 font-medium">{lib.reports_this_month}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">{fmtDateTime(lib.last_active_at)}</td>
                <td className="px-4 py-3">
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-1.5 rounded border disabled:opacity-40 hover:bg-slate-100"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-slate-600">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-1.5 rounded border disabled:opacity-40 hover:bg-slate-100"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}
