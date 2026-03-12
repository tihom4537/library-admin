import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, BookOpen, ClipboardList, GraduationCap } from 'lucide-react'
import api from '@/lib/api'
import { Badge } from '@/components/Badge'
import { fmtDate, fmtDateTime } from '@/lib/utils'

interface LibrarianDetail {
  id: string
  name: string
  phone: string
  library_name: string
  library_id: string | null
  district: string | null
  taluk: string | null
  gram_panchayat: string | null
  status: string
  language_pref: string
  last_active_at: string | null
  onboarded_at: string | null
  reports_this_month: number
  total_reports: number
  recent_reports: {
    id: string
    activity_title: string | null
    conducted_date: string | null
    approximate_children_count: string | null
    librarian_feedback: string | null
    reported_via: string
    created_at: string
  }[]
  learning_progress: {
    module_id: string
    module_title: string
    sent_at: string | null
    practice_completed: boolean
    librarian_outcome: string | null
  }[]
}

const childrenLabel: Record<string, string> = {
  lt10: '< 10', ten_twenty: '10–20', twenty_thirty: '20–30', gt30: '> 30',
}

export function LibrarianDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [lib, setLib] = useState<LibrarianDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/librarians/${id}`)
      .then(r => setLib(r.data))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="p-10 text-slate-400">Loading…</div>
  if (!lib) return <div className="p-10 text-slate-400">Librarian not found</div>

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-sm text-slate-500 hover:text-blue-600 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back to directory
      </button>

      {/* Profile Card */}
      <div className="bg-white rounded-xl border shadow-sm p-6">
        <div className="flex items-start gap-5">
          <div className="bg-blue-100 text-blue-700 font-bold text-2xl w-16 h-16 rounded-full flex items-center justify-center shrink-0">
            {lib.name[0].toUpperCase()}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-xl font-bold text-slate-800">{lib.name}</h1>
              <Badge label={lib.status} status={lib.status} />
            </div>
            <p className="text-sm text-slate-500 mt-1 flex items-center gap-2">
              <BookOpen className="w-4 h-4" /> {lib.library_name}
              {lib.library_id && <span className="text-slate-400">#{lib.library_id}</span>}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
              <Kv label="Phone" value={lib.phone} />
              <Kv label="District" value={lib.district} />
              <Kv label="Taluk" value={lib.taluk} />
              <Kv label="Gram Panchayat" value={lib.gram_panchayat} />
              <Kv label="Language" value={lib.language_pref?.toUpperCase()} />
              <Kv label="Onboarded" value={fmtDate(lib.onboarded_at)} />
              <Kv label="Last Active" value={fmtDateTime(lib.last_active_at)} />
              <Kv label="Reports This Month" value={String(lib.reports_this_month)} />
            </div>
          </div>
          <div className="text-right shrink-0">
            <p className="text-3xl font-bold text-blue-600">{lib.total_reports}</p>
            <p className="text-xs text-slate-400">Total reports</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity Reports */}
        <div className="bg-white rounded-xl border shadow-sm">
          <div className="px-5 py-4 border-b flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-slate-500" />
            <h2 className="font-semibold text-slate-800">Recent Reports</h2>
            <Badge label={`${lib.recent_reports.length}`} className="ml-auto" />
          </div>
          <div className="divide-y max-h-80 overflow-y-auto">
            {lib.recent_reports.length === 0 && (
              <p className="text-sm text-slate-400 text-center py-8">No reports yet</p>
            )}
            {lib.recent_reports.map(r => (
              <div key={r.id} className="px-4 py-3">
                <p className="text-sm font-medium text-slate-700">{r.activity_title ?? 'Activity'}</p>
                <div className="flex items-center gap-3 mt-1 flex-wrap">
                  {r.conducted_date && (
                    <span className="text-xs text-slate-500">{fmtDate(r.conducted_date)}</span>
                  )}
                  {r.approximate_children_count && (
                    <Badge label={`${childrenLabel[r.approximate_children_count] ?? r.approximate_children_count} children`} />
                  )}
                  {r.librarian_feedback && (
                    <Badge
                      label={r.librarian_feedback.replace(/_/g, ' ')}
                      status={r.librarian_feedback === 'went_well' ? 'active' : 'inactive'}
                    />
                  )}
                  <Badge label={r.reported_via} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Learning Progress */}
        <div className="bg-white rounded-xl border shadow-sm">
          <div className="px-5 py-4 border-b flex items-center gap-2">
            <GraduationCap className="w-4 h-4 text-slate-500" />
            <h2 className="font-semibold text-slate-800">Learning Progress</h2>
          </div>
          <div className="divide-y max-h-80 overflow-y-auto">
            {lib.learning_progress.length === 0 && (
              <p className="text-sm text-slate-400 text-center py-8">No modules sent yet</p>
            )}
            {lib.learning_progress.map(p => (
              <div key={p.module_id} className="px-4 py-3 flex items-start gap-3">
                <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${p.practice_completed ? 'bg-green-500' : 'bg-slate-300'}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">{p.module_title}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    {p.sent_at && (
                      <span className="text-xs text-slate-400">Sent {fmtDate(p.sent_at)}</span>
                    )}
                    {p.practice_completed && <Badge label="Completed" status="active" />}
                    {p.librarian_outcome && (
                      <Badge
                        label={p.librarian_outcome}
                        status={p.librarian_outcome === 'done' ? 'active' : 'inactive'}
                      />
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function Kv({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-sm font-medium text-slate-700">{value ?? '—'}</p>
    </div>
  )
}
