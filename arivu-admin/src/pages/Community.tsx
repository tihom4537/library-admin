import { useState, useEffect, useCallback } from 'react'
import { format } from 'date-fns'
import { Play, FileText, CheckCircle, XCircle, Eye, Mic, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '@/lib/api'

interface ContentItem {
  id: string
  librarian_id: string
  librarian_name: string | null
  librarian_district: string | null
  content_type: string
  description: string | null
  voice_note_url: string | null
  photo_url: string | null
  status: string
  created_at: string
}

interface ContentListResponse {
  total: number
  page: number
  page_size: number
  items: ContentItem[]
}

const TYPE_LABELS: Record<string, string> = {
  story: 'Story',
  song: 'Song',
  game: 'Game',
  craft: 'Craft',
  other: 'Other',
}

const STATUS_STYLES: Record<string, string> = {
  submitted: 'bg-yellow-100 text-yellow-800',
  reviewed: 'bg-blue-100 text-blue-800',
  published: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-700',
}

export function Community() {
  const [items, setItems] = useState<ContentItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 15

  const [filterStatus, setFilterStatus] = useState('')
  const [filterType, setFilterType] = useState('')
  const [loading, setLoading] = useState(false)

  const [selected, setSelected] = useState<ContentItem | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [audioLoading, setAudioLoading] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [statusUpdating, setStatusUpdating] = useState<string | null>(null)
  const [transcript, setTranscript] = useState<string | null>(null)

  const fetchItems = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get<ContentListResponse>('/community', {
        params: {
          page,
          page_size: PAGE_SIZE,
          ...(filterStatus && { status: filterStatus }),
          ...(filterType && { content_type: filterType }),
        },
      })
      setItems(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [page, filterStatus, filterType])

  useEffect(() => { fetchItems() }, [fetchItems])

  const openDetail = async (item: ContentItem) => {
    setSelected(item)
    setAudioUrl(null)
    setTranscript(null)
  }

  const loadAudio = async () => {
    if (!selected) return
    setAudioLoading(true)
    try {
      const { data } = await api.get<{ url: string }>(`/community/${selected.id}/audio`)
      setAudioUrl(data.url)
    } catch {
      alert('Could not load audio URL')
    } finally {
      setAudioLoading(false)
    }
  }

  const handleTranscribe = async () => {
    if (!selected) return
    setTranscribing(true)
    try {
      const { data } = await api.post<{ transcript: string | null; saved: boolean }>(
        `/community/${selected.id}/transcribe`
      )
      setTranscript(data.transcript ?? 'No transcript returned')
      if (data.saved) {
        setSelected(s => s ? { ...s, description: data.transcript ?? s.description } : s)
        await fetchItems()
      }
    } catch {
      alert('Transcription failed')
    } finally {
      setTranscribing(false)
    }
  }

  const handleStatusChange = async (id: string, status: string) => {
    setStatusUpdating(id)
    try {
      const { data } = await api.put<ContentItem>(`/community/${id}/status`, { status })
      setItems(prev => prev.map(it => it.id === id ? data : it))
      if (selected?.id === id) setSelected(data)
    } finally {
      setStatusUpdating(null)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Community Content</h1>
        <p className="text-slate-500 text-sm mt-1">
          Stories, songs, games and crafts submitted by librarians for review
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-5 flex-wrap">
        <select
          value={filterStatus}
          onChange={e => { setFilterStatus(e.target.value); setPage(1) }}
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All statuses</option>
          <option value="submitted">Submitted</option>
          <option value="reviewed">Reviewed</option>
          <option value="published">Published</option>
          <option value="rejected">Rejected</option>
        </select>
        <select
          value={filterType}
          onChange={e => { setFilterType(e.target.value); setPage(1) }}
          className="border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All types</option>
          {Object.entries(TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <div className="ml-auto text-sm text-slate-400 self-center">
          {total} item{total !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50 text-left">
              <th className="px-4 py-3 font-medium text-slate-500">Librarian</th>
              <th className="px-4 py-3 font-medium text-slate-500">Type</th>
              <th className="px-4 py-3 font-medium text-slate-500">Description</th>
              <th className="px-4 py-3 font-medium text-slate-500">Media</th>
              <th className="px-4 py-3 font-medium text-slate-500">Status</th>
              <th className="px-4 py-3 font-medium text-slate-500">Submitted</th>
              <th className="px-4 py-3 font-medium text-slate-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center py-12 text-slate-400">Loading…</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-12 text-slate-400">No submissions found</td></tr>
            ) : items.map(item => (
              <tr key={item.id} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{item.librarian_name ?? '—'}</p>
                  <p className="text-xs text-slate-400">{item.librarian_district ?? '—'}</p>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                    {TYPE_LABELS[item.content_type] ?? item.content_type}
                  </span>
                </td>
                <td className="px-4 py-3 max-w-xs">
                  <p className="text-slate-600 truncate">{item.description ?? <span className="text-slate-300 italic">No description</span>}</p>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1">
                    {item.voice_note_url && <Mic className="w-4 h-4 text-blue-500" />}
                    {item.photo_url && <FileText className="w-4 h-4 text-green-500" />}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[item.status] ?? 'bg-slate-100 text-slate-600'}`}>
                    {item.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">
                  {format(new Date(item.created_at), 'MMM d, yyyy')}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1 items-center">
                    <button
                      onClick={() => openDetail(item)}
                      className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
                      title="View detail"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    {item.status !== 'published' && item.status !== 'rejected' && (
                      <>
                        <button
                          onClick={() => handleStatusChange(item.id, 'published')}
                          disabled={statusUpdating === item.id}
                          className="p-1.5 rounded-lg hover:bg-green-50 text-slate-400 hover:text-green-600 transition-colors"
                          title="Publish"
                        >
                          <CheckCircle className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleStatusChange(item.id, 'rejected')}
                          disabled={statusUpdating === item.id}
                          className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition-colors"
                          title="Reject"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
          >
            <ChevronLeft className="w-4 h-4" /> Previous
          </button>
          <span className="text-sm text-slate-500">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
          >
            Next <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Detail Panel */}
      {selected && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <div>
                <h2 className="font-semibold text-slate-800">
                  {TYPE_LABELS[selected.content_type] ?? selected.content_type} — {selected.librarian_name}
                </h2>
                <p className="text-xs text-slate-400">{selected.librarian_district}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[selected.status]}`}>
                  {selected.status}
                </span>
                <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600">✕</button>
              </div>
            </div>

            <div className="p-6 space-y-5">
              {/* Description */}
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">Description / Transcript</p>
                <p className="text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-lg p-3 min-h-[60px]">
                  {selected.description ?? <span className="text-slate-400 italic">No description yet</span>}
                </p>
                {transcript && (
                  <div className="mt-2 bg-blue-50 border border-blue-100 rounded-lg p-3 text-sm text-blue-800">
                    <strong>AI Transcript:</strong> {transcript}
                  </div>
                )}
              </div>

              {/* Photo */}
              {selected.photo_url && (
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-1">Photo</p>
                  <div className="bg-slate-100 rounded-lg p-3 text-xs text-slate-500 font-mono break-all">
                    {selected.photo_url}
                  </div>
                </div>
              )}

              {/* Audio */}
              {selected.voice_note_url && (
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-2">Voice Note</p>
                  {audioUrl ? (
                    <audio controls src={audioUrl} className="w-full" />
                  ) : (
                    <button
                      onClick={loadAudio}
                      disabled={audioLoading}
                      className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg border border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors disabled:opacity-50"
                    >
                      <Play className="w-4 h-4" />
                      {audioLoading ? 'Loading…' : 'Load audio'}
                    </button>
                  )}
                  <button
                    onClick={handleTranscribe}
                    disabled={transcribing}
                    className="mt-2 flex items-center gap-2 text-sm px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600 transition-colors disabled:opacity-50"
                  >
                    <Mic className="w-4 h-4" />
                    {transcribing ? 'Transcribing…' : 'Transcribe (Sarvam AI)'}
                  </button>
                </div>
              )}

              {/* Status actions */}
              {selected.status !== 'rejected' && (
                <div className="border-t border-slate-100 pt-4">
                  <p className="text-xs font-medium text-slate-500 mb-2">Change status</p>
                  <div className="flex gap-2 flex-wrap">
                    {selected.status !== 'reviewed' && (
                      <button
                        onClick={() => handleStatusChange(selected.id, 'reviewed')}
                        disabled={statusUpdating === selected.id}
                        className="flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg border border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors disabled:opacity-50"
                      >
                        <Eye className="w-4 h-4" /> Mark reviewed
                      </button>
                    )}
                    {selected.status !== 'published' && (
                      <button
                        onClick={() => handleStatusChange(selected.id, 'published')}
                        disabled={statusUpdating === selected.id}
                        className="flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg border border-green-300 bg-green-50 hover:bg-green-100 text-green-700 transition-colors disabled:opacity-50"
                      >
                        <CheckCircle className="w-4 h-4" /> Publish
                      </button>
                    )}
                    <button
                      onClick={() => handleStatusChange(selected.id, 'rejected')}
                      disabled={statusUpdating === selected.id}
                      className="flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg border border-red-200 bg-red-50 hover:bg-red-100 text-red-600 transition-colors disabled:opacity-50"
                    >
                      <XCircle className="w-4 h-4" /> Reject
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
