import { useState, useEffect, useCallback } from 'react'
import { format, addWeeks, subWeeks } from 'date-fns'
import { Sparkles, Send, CheckCircle, ChevronLeft, ChevronRight, Plus, Edit2, X } from 'lucide-react'
import api from '@/lib/api'

interface Nudge {
  id: string
  week_start_date: string
  nudge_type: 'monday_activity' | 'thursday_motivational'
  content_kn: string
  content_en: string | null
  status: 'draft' | 'approved' | 'sent'
  generated_by: 'ai' | 'manual'
  sent_at: string | null
  sent_count: number
  created_at: string
}

const NUDGE_LABELS: Record<string, { label: string; day: string; color: string }> = {
  monday_activity: { label: 'Monday Activity', day: 'Mon', color: 'blue' },
  thursday_motivational: { label: 'Thursday Motivational', day: 'Thu', color: 'purple' },
}

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  sent: 'bg-slate-100 text-slate-600',
}

function getMonday(d: Date): Date {
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  return new Date(d.setDate(diff))
}

export function Nudges() {
  const [weekDate, setWeekDate] = useState<Date>(() => getMonday(new Date()))
  const [nudges, setNudges] = useState<Nudge[]>([])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState<string | null>(null)
  const [sending, setSending] = useState<string | null>(null)
  const [approving, setApproving] = useState<string | null>(null)
  const [editingNudge, setEditingNudge] = useState<Nudge | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editContentEn, setEditContentEn] = useState('')
  const [saving, setSaving] = useState(false)
  const [sendResult, setSendResult] = useState<{ id: string; succeeded: number; failed: number } | null>(null)
  const [error, setError] = useState('')

  const weekStr = format(weekDate, 'yyyy-MM-dd')

  const fetchNudges = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get<Nudge[]>('/nudges', { params: { week: weekStr, page_size: 10 } })
      setNudges(data)
    } catch {
      setNudges([])
    } finally {
      setLoading(false)
    }
  }, [weekStr])

  useEffect(() => { fetchNudges() }, [fetchNudges])

  const nudgeByType = (type: string) => nudges.find(n => n.nudge_type === type) ?? null

  const handleAIDraft = async (nudge_type: string) => {
    setGenerating(nudge_type)
    setError('')
    try {
      await api.post('/nudges/ai-draft', { week_start_date: weekStr, nudge_type, recent_activities: [] })
      await fetchNudges()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      setError(err?.response?.data?.detail ?? 'AI generation failed')
    } finally {
      setGenerating(null)
    }
  }

  const handleApprove = async (id: string) => {
    setApproving(id)
    try {
      await api.post(`/nudges/${id}/approve`)
      await fetchNudges()
    } finally {
      setApproving(null)
    }
  }

  const handleSend = async (id: string) => {
    if (!confirm('Send this nudge to all onboarded librarians?')) return
    setSending(id)
    try {
      const { data } = await api.post(`/nudges/${id}/send`)
      setSendResult({ id, succeeded: data.succeeded, failed: data.failed })
      await fetchNudges()
    } catch {
      setError('Send failed')
    } finally {
      setSending(null)
    }
  }

  const openEdit = (nudge: Nudge) => {
    setEditingNudge(nudge)
    setEditContent(nudge.content_kn)
    setEditContentEn(nudge.content_en ?? '')
  }

  const handleSaveEdit = async () => {
    if (!editingNudge) return
    setSaving(true)
    try {
      await api.put(`/nudges/${editingNudge.id}`, {
        content_kn: editContent,
        content_en: editContentEn || null,
      })
      await fetchNudges()
      setEditingNudge(null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Weekly Nudges</h1>
        <p className="text-slate-500 text-sm mt-1">
          AI-generated motivational nudges sent to librarians each week
        </p>
      </div>

      {/* Week Navigator */}
      <div className="flex items-center gap-4 mb-6 bg-white rounded-xl border border-slate-200 px-5 py-3">
        <button
          onClick={() => setWeekDate(w => subWeeks(w, 1))}
          className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
        >
          <ChevronLeft className="w-5 h-5 text-slate-600" />
        </button>
        <div className="flex-1 text-center">
          <p className="font-semibold text-slate-800">
            Week of {format(weekDate, 'MMMM d, yyyy')}
          </p>
          <p className="text-xs text-slate-400">
            {format(weekDate, 'MMM d')} — {format(addWeeks(weekDate, 1), 'MMM d')}
          </p>
        </div>
        <button
          onClick={() => setWeekDate(w => addWeeks(w, 1))}
          className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
        >
          <ChevronRight className="w-5 h-5 text-slate-600" />
        </button>
        <button
          onClick={() => setWeekDate(getMonday(new Date()))}
          className="text-xs text-blue-600 hover:text-blue-700 font-medium px-3 py-1 rounded-lg border border-blue-200 hover:bg-blue-50 transition-colors"
        >
          This week
        </button>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {sendResult && (
        <div className="mb-4 bg-green-50 border border-green-200 text-green-800 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
          <span>Nudge sent: {sendResult.succeeded} delivered, {sendResult.failed} failed</span>
          <button onClick={() => setSendResult(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading…</div>
      ) : (
        <div className="space-y-4">
          {(['monday_activity', 'thursday_motivational'] as const).map(nudge_type => {
            const meta = NUDGE_LABELS[nudge_type]
            const nudge = nudgeByType(nudge_type)

            return (
              <div key={nudge_type} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                {/* Header */}
                <div className={`px-5 py-3 flex items-center justify-between border-b border-slate-100 ${
                  meta.color === 'blue' ? 'bg-blue-50' : 'bg-purple-50'
                }`}>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                      meta.color === 'blue' ? 'bg-blue-200 text-blue-800' : 'bg-purple-200 text-purple-800'
                    }`}>
                      {meta.day}
                    </span>
                    <span className="font-semibold text-slate-700 text-sm">{meta.label}</span>
                  </div>
                  {nudge && (
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[nudge.status]}`}>
                      {nudge.status}
                      {nudge.generated_by === 'ai' && ' · AI'}
                    </span>
                  )}
                </div>

                {/* Body */}
                <div className="px-5 py-4">
                  {nudge ? (
                    <>
                      <p className="text-sm text-slate-800 leading-relaxed">{nudge.content_kn}</p>
                      {nudge.content_en && (
                        <p className="text-xs text-slate-400 mt-2 italic">{nudge.content_en}</p>
                      )}
                      {nudge.sent_at && (
                        <p className="text-xs text-slate-400 mt-2">
                          Sent {format(new Date(nudge.sent_at), 'MMM d, h:mm a')} · {nudge.sent_count} recipients
                        </p>
                      )}

                      {nudge.status !== 'sent' && (
                        <div className="flex gap-2 mt-4 flex-wrap">
                          <button
                            onClick={() => openEdit(nudge)}
                            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
                          >
                            <Edit2 className="w-3 h-3" /> Edit
                          </button>
                          {nudge.status === 'draft' && (
                            <button
                              onClick={() => handleApprove(nudge.id)}
                              disabled={approving === nudge.id}
                              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-green-300 bg-green-50 hover:bg-green-100 text-green-700 transition-colors disabled:opacity-50"
                            >
                              <CheckCircle className="w-3 h-3" />
                              {approving === nudge.id ? 'Approving…' : 'Approve'}
                            </button>
                          )}
                          {nudge.status === 'approved' && (
                            <button
                              onClick={() => handleSend(nudge.id)}
                              disabled={sending === nudge.id}
                              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-50"
                            >
                              <Send className="w-3 h-3" />
                              {sending === nudge.id ? 'Sending…' : 'Send to all'}
                            </button>
                          )}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="flex items-center justify-between py-2">
                      <p className="text-sm text-slate-400 italic">No nudge for this week</p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleAIDraft(nudge_type)}
                          disabled={generating === nudge_type}
                          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors disabled:opacity-50"
                        >
                          <Sparkles className="w-3 h-3" />
                          {generating === nudge_type ? 'Generating…' : 'AI Generate'}
                        </button>
                        <button
                          onClick={() => openEdit({ id: '', week_start_date: weekStr, nudge_type, content_kn: '', content_en: '', status: 'draft', generated_by: 'manual', sent_at: null, sent_count: 0, created_at: '' } as Nudge)}
                          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors"
                        >
                          <Plus className="w-3 h-3" /> Write manually
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Edit / Create Modal */}
      {editingNudge !== null && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h2 className="text-base font-semibold text-slate-800">
                {editingNudge.id ? 'Edit Nudge' : 'Create Nudge'}
              </h2>
              <button onClick={() => setEditingNudge(null)}>
                <X className="w-5 h-5 text-slate-400 hover:text-slate-600" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">
                  Kannada content <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={editContent}
                  onChange={e => setEditContent(e.target.value)}
                  rows={4}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="ಕನ್ನಡದಲ್ಲಿ ಸಂದೇಶ ಬರೆಯಿರಿ…"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">English (optional)</label>
                <textarea
                  value={editContentEn}
                  onChange={e => setEditContentEn(e.target.value)}
                  rows={3}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="English translation…"
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-3">
              <button
                onClick={() => setEditingNudge(null)}
                className="px-4 py-2 text-sm rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  if (!editingNudge.id) {
                    // Create new
                    setSaving(true)
                    try {
                      await api.post('/nudges', {
                        week_start_date: editingNudge.week_start_date,
                        nudge_type: editingNudge.nudge_type,
                        content_kn: editContent,
                        content_en: editContentEn || null,
                      })
                      await fetchNudges()
                      setEditingNudge(null)
                    } finally {
                      setSaving(false)
                    }
                  } else {
                    await handleSaveEdit()
                  }
                }}
                disabled={saving || !editContent.trim()}
                className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
