import { useEffect, useState } from 'react'
import {
  Users, ClipboardList, Camera, CheckCircle,
  AlertCircle, RefreshCw, Send
} from 'lucide-react'
import api from '@/lib/api'
import { StatCard } from '@/components/StatCard'
import { Badge } from '@/components/Badge'
import { fmtDateTime, fmtDate } from '@/lib/utils'

interface Stats {
  active_librarians_count: number
  reports_this_month: number
  photos_count: number
  mandatory_compliance_pct: number
  inactive_librarians_count: number
  computed_at: string
}

interface FeedItem {
  report_id: string
  librarian_name: string
  district: string | null
  activity_title: string | null
  conducted_date: string | null
  photo_urls: string[]
  librarian_feedback: string | null
  reported_at: string
}

interface InactiveLibrarian {
  id: string
  name: string
  district: string | null
  phone: string
}

export function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [feed, setFeed] = useState<FeedItem[]>([])
  const [inactive, setInactive] = useState<InactiveLibrarian[]>([])
  const [nudging, setNudging] = useState(false)
  const [nudgeResult, setNudgeResult] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    const [s, f, i] = await Promise.all([
      api.get('/dashboard/stats'),
      api.get('/dashboard/feed?page_size=10'),
      api.get('/dashboard/inactive'),
    ])
    setStats(s.data)
    setFeed(f.data)
    setInactive(i.data)
  }

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function sendNudge() {
    if (selected.size === 0) return
    setNudging(true)
    setNudgeResult(null)
    try {
      const res = await api.post('/librarians/nudge', {
        librarian_ids: [...selected],
        template_name: 'librarian_nudge',
      })
      const { succeeded, failed } = res.data
      setNudgeResult(`Sent: ${succeeded} ✓  Failed: ${failed}`)
      setSelected(new Set())
    } catch {
      setNudgeResult('Failed to send nudge')
    } finally {
      setNudging(false)
    }
  }

  const feedbackLabel: Record<string, string> = {
    went_well: 'Went well',
    needs_improvement: 'Needs improvement',
    difficult: 'Difficult',
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
          {stats && (
            <p className="text-xs text-slate-400 mt-0.5">
              Updated {fmtDateTime(stats.computed_at)}
            </p>
          )}
        </div>
        <button
          onClick={loadAll}
          className="flex items-center gap-2 text-sm text-slate-600 hover:text-blue-600 border rounded-lg px-3 py-1.5 bg-white shadow-sm"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Stat Cards */}
      {stats && (
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
          <StatCard
            title="Active Librarians"
            value={stats.active_librarians_count}
            subtitle="Last 7 days"
            icon={Users}
            color="blue"
          />
          <StatCard
            title="Reports This Month"
            value={stats.reports_this_month}
            icon={ClipboardList}
            color="green"
          />
          <StatCard
            title="Photos Uploaded"
            value={stats.photos_count}
            subtitle="Total across reports"
            icon={Camera}
            color="purple"
          />
          <StatCard
            title="Mandatory Compliance"
            value={`${stats.mandatory_compliance_pct}%`}
            subtitle="Last 30 days"
            icon={CheckCircle}
            color="orange"
          />
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Recent Activity Feed */}
        <div className="xl:col-span-2 bg-white rounded-xl border shadow-sm">
          <div className="px-5 py-4 border-b flex items-center justify-between">
            <h2 className="font-semibold text-slate-800">Recent Activity Reports</h2>
            <Badge label={`${feed.length} shown`} />
          </div>
          <div className="divide-y max-h-[520px] overflow-y-auto">
            {feed.length === 0 && (
              <p className="text-sm text-slate-400 text-center py-10">No reports yet</p>
            )}
            {feed.map(item => (
              <div key={item.report_id} className="px-5 py-3 flex gap-3">
                {/* Photo thumbnail */}
                {item.photo_urls[0] ? (
                  <img
                    src={item.photo_urls[0]}
                    alt=""
                    className="w-14 h-14 rounded-lg object-cover shrink-0 border"
                  />
                ) : (
                  <div className="w-14 h-14 rounded-lg bg-slate-100 flex items-center justify-center shrink-0">
                    <Camera className="w-5 h-5 text-slate-400" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">
                    {item.activity_title ?? 'Activity'}
                  </p>
                  <p className="text-xs text-slate-500">
                    {item.librarian_name} · {item.district ?? '—'}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    {item.librarian_feedback && (
                      <Badge
                        label={feedbackLabel[item.librarian_feedback] ?? item.librarian_feedback}
                        status={item.librarian_feedback === 'went_well' ? 'active' : 'inactive'}
                      />
                    )}
                    <span className="text-xs text-slate-400">{fmtDate(item.conducted_date)}</span>
                  </div>
                </div>
                <span className="text-xs text-slate-400 shrink-0">{fmtDateTime(item.reported_at)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Inactive Librarians Panel */}
        <div className="bg-white rounded-xl border shadow-sm flex flex-col">
          <div className="px-5 py-4 border-b flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-orange-500" />
              <h2 className="font-semibold text-slate-800">Inactive (30d)</h2>
            </div>
            <Badge label={`${inactive.length}`} status="inactive" />
          </div>

          {nudgeResult && (
            <div className="mx-4 mt-3 bg-green-50 border border-green-200 text-green-700 text-xs rounded-lg px-3 py-2">
              {nudgeResult}
            </div>
          )}

          <div className="flex-1 overflow-y-auto max-h-72 divide-y">
            {inactive.length === 0 && (
              <p className="text-sm text-slate-400 text-center py-8">All librarians active!</p>
            )}
            {inactive.map(lib => (
              <label key={lib.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.has(lib.id)}
                  onChange={() => toggleSelect(lib.id)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">{lib.name}</p>
                  <p className="text-xs text-slate-400">{lib.district ?? '—'} · {lib.phone}</p>
                </div>
              </label>
            ))}
          </div>

          <div className="px-4 py-3 border-t">
            <button
              onClick={sendNudge}
              disabled={selected.size === 0 || nudging}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition-colors"
            >
              <Send className="w-4 h-4" />
              {nudging ? 'Sending…' : `Send Nudge (${selected.size})`}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
