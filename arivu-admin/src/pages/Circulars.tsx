import { useEffect, useState } from 'react'
import { Plus, Wand2, X, Loader2, Send, Save, ChevronDown, ChevronUp, Eye, EyeOff, FileText } from 'lucide-react'
import api from '@/lib/api'
import { Badge } from '@/components/Badge'
import { fmtDate } from '@/lib/utils'

interface Circular {
  id: string
  circular_number: string
  issue_date: string | null
  status: string
  action_item_count: number
  created_at: string
}

const empty = (): any => ({
  circular_number: '',
  issue_date: '',
  original_text: '',
  simplified_text: '',
  status: 'draft',
  action_items: [],
})

// ── Government Document Preview ──────────────────────────────────────────────

function CircularDocumentPreview({ editing }: { editing: any }) {
  const lines = (editing.simplified_text ?? '')
    .split('\n')
    .map((l: string) => l.trim())
    .filter(Boolean)

  return (
    <div
      style={{ fontFamily: "'Noto Serif Kannada', 'Times New Roman', serif" }}
      className="bg-white rounded-lg border border-slate-300 shadow-md overflow-hidden text-sm"
    >
      {/* Tricolour strip */}
      <div className="flex h-1.5">
        <div className="flex-1 bg-orange-500" />
        <div className="flex-1 bg-white border-y border-slate-200" />
        <div className="flex-1 bg-green-700" />
      </div>

      {/* Letterhead */}
      <div className="bg-slate-50 border-b border-slate-200 px-8 py-5 text-center">
        <div className="flex items-center justify-center gap-4 mb-1">
          <div className="w-12 h-12 rounded-full border-2 border-slate-400 flex items-center justify-center bg-white shrink-0">
            <span className="text-[9px] font-bold text-slate-600 leading-tight text-center px-0.5">ಕರ್ನಾಟಕ<br />ಸರ್ಕಾರ</span>
          </div>
          <div className="text-left">
            <p className="text-xs font-bold text-slate-800 uppercase tracking-wide leading-snug">
              Government of Karnataka
            </p>
            <p className="text-[11px] text-slate-600">ಕರ್ನಾಟಕ ಸರ್ಕಾರ</p>
            <p className="text-[11px] text-slate-500 mt-0.5">
              ಸಾರ್ವಜನಿಕ ಗ್ರಂಥಾಲಯ ಇಲಾಖೆ &nbsp;/&nbsp; Department of Public Libraries
            </p>
          </div>
        </div>
      </div>

      {/* Ref + Date */}
      <div className="px-8 py-3 flex items-start justify-between border-b border-slate-200 bg-white">
        <div>
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">ಸಂಖ್ಯೆ / Ref. No.</p>
          <p className="font-bold text-slate-800 text-sm mt-0.5">
            {editing.circular_number || <span className="text-slate-400 italic font-normal">—</span>}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">ದಿನಾಂಕ / Date</p>
          <p className="font-bold text-slate-800 text-sm mt-0.5">
            {editing.issue_date
              ? new Date(editing.issue_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' })
              : <span className="text-slate-400 italic font-normal">—</span>
            }
          </p>
        </div>
      </div>

      {/* Body */}
      <div className="px-8 py-6 space-y-5 bg-white">
        {/* To */}
        <div>
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">ಸೇವೆಗೆ / To</p>
          <p className="text-slate-700 text-xs leading-relaxed">
            ಎಲ್ಲಾ ಜಿಲ್ಲಾ ಗ್ರಂಥಾಲಯ ಅಧಿಕಾರಿಗಳು ಮತ್ತು ಗ್ರಾಮ ಗ್ರಂಥಪಾಲರು,<br />
            ಕರ್ನಾಟಕ ರಾಜ್ಯ.
          </p>
        </div>

        <div className="border-t border-dashed border-slate-200 pt-5">
          <p className="text-slate-700 mb-4 leading-relaxed text-xs">ಮಹಾಶಯರೇ / ಮಹಾಶಯೆಯರೇ,</p>

          {lines.length === 0 ? (
            <p className="text-slate-400 italic text-xs">
              ಸರಳ ಸಾರಾಂಶ ಇಲ್ಲಿ ತೋರಿಸಲಾಗುತ್ತದೆ… (AI Simplify ಬಳಸಿ ಅಥವಾ ನೇರವಾಗಿ ಟೈಪ್ ಮಾಡಿ)
            </p>
          ) : (
            <ul className="space-y-2.5">
              {lines.map((line: string, i: number) => {
                const cleaned = line.replace(/^[•·▪▸\-*]\s*/, '')
                return (
                  <li key={i} className="flex items-start gap-2.5 text-slate-700 text-xs leading-relaxed">
                    <span className="mt-0.5 shrink-0 w-5 h-5 rounded-full bg-orange-100 border border-orange-300 flex items-center justify-center text-[9px] font-bold text-orange-700">
                      {i + 1}
                    </span>
                    <span>{cleaned}</span>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Action Items */}
        {editing.action_items?.length > 0 && (
          <div className="border-t border-slate-200 pt-5">
            <p className="text-[10px] font-bold text-slate-600 uppercase tracking-wider mb-3">
              ಕ್ರಮ ಅಂಶಗಳು / Action Items
            </p>
            <div className="space-y-2.5">
              {editing.action_items.map((item: any, i: number) => (
                <div key={i} className="flex items-start gap-3 text-xs bg-blue-50 rounded-lg px-3 py-2.5 border border-blue-100">
                  <span className="shrink-0 w-5 h-5 rounded bg-blue-600 flex items-center justify-center font-bold text-white text-[10px]">
                    {i + 1}
                  </span>
                  <span className="flex-1 text-slate-700 leading-relaxed">{item.title_kn || '—'}</span>
                  {item.due_date && (
                    <span className="shrink-0 text-slate-500 text-[10px] bg-white px-2 py-0.5 rounded border border-slate-200 whitespace-nowrap">
                      📅 {new Date(item.due_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer / Signature */}
      <div className="px-8 py-5 bg-slate-50 border-t border-slate-200 flex items-end justify-between">
        <div>
          <div className="w-32 border-b border-slate-500 mb-1.5" />
          <p className="text-[10px] font-semibold text-slate-700">ಮೇಲ್ನೋಟ ಅಧಿಕಾರಿ</p>
          <p className="text-[10px] text-slate-500">ಸಾರ್ವಜನಿಕ ಗ್ರಂಥಾಲಯ ಇಲಾಖೆ</p>
          <p className="text-[10px] text-slate-500">ಕರ್ನಾಟಕ ಸರ್ಕಾರ</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-slate-400 italic">Arivu Digital Library Portal</p>
          <p className="text-[10px] text-slate-400">ಆಂತರಿಕ ಬಳಕೆ ಮಾತ್ರ / Internal Use Only</p>
        </div>
      </div>

      {/* Bottom tricolour */}
      <div className="flex h-1.5">
        <div className="flex-1 bg-orange-500" />
        <div className="flex-1 bg-white border-y border-slate-200" />
        <div className="flex-1 bg-green-700" />
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export function Circulars() {
  const [list, setList]                   = useState<Circular[]>([])
  const [statusFilter, setStatusFilter]   = useState('')
  const [loading, setLoading]             = useState(false)
  const [editing, setEditing]             = useState<any | null>(null)
  const [saving, setSaving]               = useState(false)
  const [aiLoading, setAiLoading]         = useState(false)
  const [sending, setSending]             = useState(false)
  const [showOriginal, setShowOriginal]   = useState(false)
  const [showPreview, setShowPreview]     = useState(true)

  useEffect(() => { load() }, [statusFilter])

  async function load() {
    setLoading(true)
    try {
      const p = new URLSearchParams()
      if (statusFilter) p.set('status', statusFilter)
      const r = await api.get(`/circulars?${p}`)
      setList(r.data)
    } finally { setLoading(false) }
  }

  async function openEdit(id: string) {
    const r = await api.get(`/circulars/${id}`)
    setEditing(r.data)
    setShowOriginal(false)
    setShowPreview(true)
  }

  async function save() {
    if (!editing) return
    setSaving(true)
    try {
      const payload = {
        circular_number: editing.circular_number,
        issue_date: editing.issue_date || null,
        original_text: editing.original_text,
        simplified_text: editing.simplified_text,
        status: editing.status,
        action_items: editing.action_items,
      }
      if (editing.id) {
        await api.put(`/circulars/${editing.id}`, payload)
      } else {
        await api.post('/circulars', payload)
      }
      setEditing(null)
      load()
    } catch (e: any) {
      alert(e.response?.data?.detail ?? 'Save failed')
    } finally { setSaving(false) }
  }

  async function aiSimplify() {
    if (!editing?.id) { alert('Save the circular first, then use AI Simplify'); return }
    setAiLoading(true)
    try {
      const r = await api.post(`/circulars/${editing.id}/simplify`)
      const { simplified_kn, action_items } = r.data
      setEditing((prev: any) => ({
        ...prev,
        simplified_text: simplified_kn,
        action_items: action_items.map((ai: any, i: number) => ({
          title_kn: ai.title_kn,
          due_date: ai.due_date ?? null,
          order: i,
        })),
      }))
    } catch (e: any) {
      alert('AI simplify failed: ' + (e.response?.data?.detail ?? e.message))
    } finally { setAiLoading(false) }
  }

  async function sendCircular() {
    if (!editing?.id) return
    if (!confirm('Send this circular to all librarians?')) return
    setSending(true)
    try {
      await api.post(`/circulars/${editing.id}/send`)
      setEditing((prev: any) => ({ ...prev, status: 'published' }))
      load()
    } catch (e: any) {
      alert(e.response?.data?.detail ?? 'Send failed')
    } finally { setSending(false) }
  }

  function addActionItem() {
    setEditing((prev: any) => ({
      ...prev,
      action_items: [
        ...prev.action_items,
        { title_kn: '', due_date: '', order: prev.action_items.length },
      ],
    }))
  }

  function updateItem(idx: number, field: string, val: string) {
    setEditing((prev: any) => {
      const items = [...prev.action_items]
      items[idx] = { ...items[idx], [field]: val }
      return { ...prev, action_items: items }
    })
  }

  // ── Editor (document layout) ─────────────────────────────────────────────────
  if (editing !== null) {
    return (
      <div className="flex-1 overflow-hidden flex flex-col h-full">
        {/* Top bar */}
        <div className="shrink-0 bg-white border-b px-6 py-3 flex items-center gap-4 flex-wrap">
          <button
            onClick={() => setEditing(null)}
            className="flex items-center gap-1.5 text-slate-500 hover:text-slate-800 text-sm"
          >
            ← Back
          </button>
          <span className="text-slate-300 hidden sm:block">|</span>
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-orange-500" />
            <h1 className="font-bold text-slate-800 text-base">
              {editing.id ? (editing.circular_number || 'Untitled Circular') : 'New Circular'}
            </h1>
            <Badge label={editing.status} status={editing.status} />
          </div>
          <div className="ml-auto flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setShowPreview(p => !p)}
              className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                showPreview
                  ? 'bg-blue-50 border-blue-200 text-blue-700'
                  : 'border-slate-200 text-slate-500 hover:bg-slate-50'
              }`}
            >
              {showPreview ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
              Preview
            </button>
            <button
              onClick={aiSimplify}
              disabled={aiLoading}
              className="flex items-center gap-1.5 text-xs text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 px-3 py-1.5 rounded-lg transition-colors"
            >
              {aiLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
              {aiLoading ? 'Simplifying…' : 'AI Simplify'}
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-900 text-white px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              {saving ? 'Saving…' : 'Save Draft'}
            </button>
            {editing.id && editing.status !== 'published' && (
              <button
                onClick={sendCircular}
                disabled={sending}
                className="flex items-center gap-1.5 text-xs bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
              >
                {sending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                {sending ? 'Sending…' : 'Send to Librarians'}
              </button>
            )}
          </div>
        </div>

        {/* Split panel */}
        <div className="flex-1 overflow-hidden flex">
          {/* Left: Edit form */}
          <div className="w-80 shrink-0 border-r bg-slate-50 overflow-y-auto p-5 space-y-4">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Document Fields</p>

            <Field label="Circular Number *">
              <input
                value={editing.circular_number}
                onChange={e => setEditing((p: any) => ({ ...p, circular_number: e.target.value }))}
                placeholder="e.g. ಕಪಂರಾಆ/ಅಭಿವ್ಯ/001/2026"
                className="input-base"
              />
            </Field>

            <Field label="Issue Date">
              <input
                type="date"
                value={editing.issue_date ?? ''}
                onChange={e => setEditing((p: any) => ({ ...p, issue_date: e.target.value }))}
                className="input-base"
              />
            </Field>

            <Field label="Status">
              <select
                value={editing.status}
                onChange={e => setEditing((p: any) => ({ ...p, status: e.target.value }))}
                className="input-base"
              >
                <option value="draft">Draft</option>
                <option value="published">Published</option>
              </select>
            </Field>

            {/* Original text */}
            <div className="border-t border-slate-200 pt-4">
              <button
                onClick={() => setShowOriginal(p => !p)}
                className="flex items-center gap-2 text-xs font-semibold text-slate-600 mb-2 w-full text-left hover:text-slate-800"
              >
                {showOriginal ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                Original Circular Text
              </button>
              {showOriginal && (
                <textarea
                  rows={7}
                  value={editing.original_text ?? ''}
                  onChange={e => setEditing((p: any) => ({ ...p, original_text: e.target.value }))}
                  placeholder="Paste the original circular text here…"
                  className="input-base resize-none text-xs"
                />
              )}
            </div>

            {/* Simplified text */}
            <div className="border-t border-slate-200 pt-4">
              <Field label="Simplified Summary (Kannada)">
                <textarea
                  rows={7}
                  value={editing.simplified_text ?? ''}
                  onChange={e => setEditing((p: any) => ({ ...p, simplified_text: e.target.value }))}
                  placeholder="• ಬಿಂದು ೧&#10;• ಬಿಂದು ೨&#10;• ಬಿಂದು ೩"
                  className="input-base resize-none text-xs leading-relaxed"
                />
              </Field>
            </div>

            {/* Action items */}
            <div className="border-t border-slate-200 pt-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-slate-600">Action Items</p>
                <button
                  onClick={addActionItem}
                  className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                  <Plus className="w-3 h-3" /> Add
                </button>
              </div>
              <div className="space-y-2">
                {editing.action_items.map((item: any, i: number) => (
                  <div key={i} className="bg-white border border-slate-200 rounded-lg p-2.5 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className="w-4 h-4 rounded bg-blue-100 flex items-center justify-center text-[9px] font-bold text-blue-700 shrink-0">
                        {i + 1}
                      </span>
                      <button
                        onClick={() => setEditing((p: any) => ({
                          ...p,
                          action_items: p.action_items.filter((_: any, j: number) => j !== i),
                        }))}
                        className="ml-auto text-slate-300 hover:text-red-500"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <input
                      value={item.title_kn}
                      onChange={e => updateItem(i, 'title_kn', e.target.value)}
                      placeholder="ಕ್ರಮ ಅಂಶ ವಿವರಣೆ (Kannada)"
                      className="input-base text-xs"
                    />
                    <input
                      type="date"
                      value={item.due_date ?? ''}
                      onChange={e => updateItem(i, 'due_date', e.target.value)}
                      className="input-base text-xs"
                    />
                  </div>
                ))}
                {editing.action_items.length === 0 && (
                  <p className="text-[11px] text-slate-400 text-center py-3 border border-dashed rounded-lg">
                    AI Simplify will extract action items automatically
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Right: Document preview */}
          {showPreview ? (
            <div className="flex-1 overflow-y-auto bg-slate-200 p-8">
              <div className="max-w-2xl mx-auto">
                <p className="text-[10px] text-slate-400 text-center mb-4 uppercase tracking-widest font-semibold">
                  Live Document Preview
                </p>
                <CircularDocumentPreview editing={editing} />
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center bg-slate-100 text-slate-400 text-sm gap-2">
              Preview hidden — click <Eye className="w-4 h-4" /> to show
            </div>
          )}
        </div>

        <style>{`.input-base { width: 100%; border: 1px solid #e2e8f0; border-radius: 0.5rem; padding: 0.5rem 0.75rem; font-size: 0.875rem; outline: none; } .input-base:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }`}</style>
      </div>
    )
  }

  // ── List ──────────────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Circulars</h1>
          <p className="text-sm text-slate-500 mt-0.5">Department circulars simplified for librarians</p>
        </div>
        <button
          onClick={() => setEditing(empty())}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 shadow-sm"
        >
          <Plus className="w-4 h-4" /> New Circular
        </button>
      </div>

      <div className="bg-white rounded-xl border shadow-sm p-4 flex gap-3 items-center">
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
        </select>
        <span className="text-sm text-slate-500 ml-auto">{list.length} circulars</span>
      </div>

      {/* Circular cards */}
      {loading ? (
        <div className="text-center py-16 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin mx-auto" />
        </div>
      ) : list.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No circulars yet</p>
          <p className="text-xs mt-1">Create one manually or use the Activity Calendar to generate activity circulars.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {list.map(c => (
            <div
              key={c.id}
              onClick={() => openEdit(c.id)}
              className="bg-white rounded-xl border shadow-sm hover:border-blue-300 hover:shadow-md transition-all cursor-pointer overflow-hidden group"
            >
              {/* Tricolour strip */}
              <div className="flex h-1">
                <div className="flex-1 bg-orange-400" />
                <div className="flex-1 bg-white" />
                <div className="flex-1 bg-green-600" />
              </div>
              <div className="px-5 py-4 flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-orange-50 border border-orange-200 flex items-center justify-center shrink-0">
                  <FileText className="w-5 h-5 text-orange-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-bold text-slate-800 text-sm">{c.circular_number}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Issued: {fmtDate(c.issue_date)} · {c.action_item_count} action items
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <Badge label={c.status} status={c.status} />
                  <span className="text-xs text-slate-400">{fmtDate(c.created_at)}</span>
                  <span className="text-slate-400 text-xs group-hover:text-blue-600 transition-colors">Open →</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      {children}
    </div>
  )
}
