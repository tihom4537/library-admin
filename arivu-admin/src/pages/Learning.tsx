import { useState, useEffect, useCallback } from 'react'
import { Plus, Sparkles, Send, BookOpen, ChevronRight, CheckCircle, X, Trash2, Eye, EyeOff, BarChart2 } from 'lucide-react'
import api from '@/lib/api'

interface Module {
  id: string
  title_kn: string
  category: string | null
  difficulty: string
  estimated_minutes: number
  sequence_order: number
  active: boolean
  published: boolean
  step_one_heading_kn: string | null
  step_one_text_kn: string | null
  step_one_image_url: string | null
  step_two_heading_kn: string | null
  step_two_text_kn: string | null
  step_two_image_url: string | null
  step_three_heading_kn: string | null
  step_three_text_kn: string | null
  step_three_image_url: string | null
  practice_prompt_kn: string | null
  created_at: string
  updated_at: string
}

interface ProgressByDistrict {
  district: string
  sent_count: number
  viewed_count: number
  practice_completed_count: number
  completion_pct: number
}

interface ModuleProgress {
  module_id: string
  module_title: string
  total_sent: number
  total_viewed: number
  total_practice_completed: number
  by_district: ProgressByDistrict[]
}

const CATEGORIES = ['computer', 'library', 'reading', 'craft', 'other']
const DIFFICULTIES = ['beginner', 'intermediate', 'advanced']

const emptyForm = (): Partial<Module> => ({
  title_kn: '',
  category: 'library',
  difficulty: 'beginner',
  estimated_minutes: 5,
  sequence_order: 0,
  step_one_heading_kn: '',
  step_one_text_kn: '',
  step_one_image_url: '',
  step_two_heading_kn: '',
  step_two_text_kn: '',
  step_two_image_url: '',
  step_three_heading_kn: '',
  step_three_text_kn: '',
  step_three_image_url: '',
  practice_prompt_kn: '',
})

export function Learning() {
  const [modules, setModules] = useState<Module[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filterPublished, setFilterPublished] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [search, setSearch] = useState('')

  const [selected, setSelected] = useState<Module | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [form, setForm] = useState<Partial<Module>>(emptyForm())
  const [saving, setSaving] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [sending, setSending] = useState(false)
  const [sendResult, setSendResult] = useState<{ attempted: number; succeeded: number; failed: number } | null>(null)

  const [showAIPanel, setShowAIPanel] = useState(false)
  const [aiText, setAIText] = useState('')
  const [aiTopic, setAITopic] = useState('')
  const [aiLoading, setAILoading] = useState(false)

  const [showProgress, setShowProgress] = useState(false)
  const [progress, setProgress] = useState<ModuleProgress | null>(null)
  const [progressLoading, setProgressLoading] = useState(false)

  const fetchModules = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get<{ total: number; items: Module[] }>('/learning/modules', {
        params: {
          page_size: 50,
          ...(filterPublished && { published: filterPublished }),
          ...(filterCategory && { category: filterCategory }),
          ...(search && { search }),
        },
      })
      setModules(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [filterPublished, filterCategory, search])

  useEffect(() => { fetchModules() }, [fetchModules])

  const openNew = () => {
    setSelected(null)
    setIsNew(true)
    setForm(emptyForm())
    setSendResult(null)
  }

  const openEdit = (mod: Module) => {
    setSelected(mod)
    setIsNew(false)
    setForm({ ...mod })
    setSendResult(null)
    setShowProgress(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      if (isNew) {
        const { data } = await api.post<Module>('/learning/modules', form)
        setModules(prev => [data, ...prev])
        setSelected(data)
        setIsNew(false)
        setForm({ ...data })
      } else if (selected) {
        const { data } = await api.put<Module>(`/learning/modules/${selected.id}`, form)
        setModules(prev => prev.map(m => m.id === data.id ? data : m))
        setSelected(data)
        setForm({ ...data })
      }
    } finally {
      setSaving(false)
    }
  }

  const handlePublish = async () => {
    if (!selected) return
    setPublishing(true)
    try {
      const { data } = await api.post<Module>(`/learning/modules/${selected.id}/publish`)
      setModules(prev => prev.map(m => m.id === data.id ? data : m))
      setSelected(data)
      setForm({ ...data })
    } finally {
      setPublishing(false)
    }
  }

  const handleSend = async () => {
    if (!selected) return
    if (!confirm('Send this module to all onboarded librarians now?')) return
    setSending(true)
    try {
      const { data } = await api.post<{ attempted: number; succeeded: number; failed: number }>(
        `/learning/modules/${selected.id}/send`
      )
      setSendResult(data)
    } catch {
      alert('Send failed')
    } finally {
      setSending(false)
    }
  }

  const handleDeactivate = async () => {
    if (!selected) return
    if (!confirm('Deactivate this module? It will be hidden from the list.')) return
    await api.delete(`/learning/modules/${selected.id}`)
    setModules(prev => prev.filter(m => m.id !== selected.id))
    setSelected(null)
    setIsNew(false)
  }

  const handleAIBreakdown = async () => {
    if (!aiText.trim()) return
    setAILoading(true)
    try {
      const { data } = await api.post('/learning/modules/ai-breakdown', {
        text: aiText,
        topic: aiTopic || null,
      })
      setForm(prev => ({
        ...prev,
        title_kn: data.title_kn || prev.title_kn,
        category: data.category || prev.category,
        estimated_minutes: data.estimated_minutes || prev.estimated_minutes,
        step_one_heading_kn: data.step_one_heading_kn || '',
        step_one_text_kn: data.step_one_text_kn || '',
        step_two_heading_kn: data.step_two_heading_kn || '',
        step_two_text_kn: data.step_two_text_kn || '',
        step_three_heading_kn: data.step_three_heading_kn || '',
        step_three_text_kn: data.step_three_text_kn || '',
        practice_prompt_kn: data.practice_prompt_kn || '',
      }))
      setShowAIPanel(false)
      setAIText('')
    } catch {
      alert('AI breakdown failed')
    } finally {
      setAILoading(false)
    }
  }

  const loadProgress = async () => {
    if (!selected) return
    setProgressLoading(true)
    try {
      const { data } = await api.get<ModuleProgress>(`/learning/modules/${selected.id}/progress`)
      setProgress(data)
      setShowProgress(true)
    } finally {
      setProgressLoading(false)
    }
  }

  const f = (key: keyof Module) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [key]: e.target.value }))

  const fNum = (key: keyof Module) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(prev => ({ ...prev, [key]: parseInt(e.target.value) || 0 }))

  const isEditorDirty = isNew || (selected && JSON.stringify(form) !== JSON.stringify(selected))

  return (
    <div className="flex h-full">
      {/* ── LEFT: Module List ──────────────────────────────────── */}
      <div className="w-80 shrink-0 border-r border-slate-200 flex flex-col bg-white">
        <div className="px-4 py-4 border-b border-slate-100">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-base font-bold text-slate-800">Micro-Learning</h1>
            <button
              onClick={openNew}
              className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
            >
              <Plus className="w-3 h-3" /> New
            </button>
          </div>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search modules…"
            className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-2"
          />
          <div className="flex gap-2">
            <select
              value={filterPublished}
              onChange={e => setFilterPublished(e.target.value)}
              className="flex-1 border border-slate-200 rounded-lg px-2 py-1 text-xs bg-white focus:outline-none"
            >
              <option value="">All</option>
              <option value="true">Published</option>
              <option value="false">Draft</option>
            </select>
            <select
              value={filterCategory}
              onChange={e => setFilterCategory(e.target.value)}
              className="flex-1 border border-slate-200 rounded-lg px-2 py-1 text-xs bg-white focus:outline-none"
            >
              <option value="">All categories</option>
              {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <p className="text-center py-8 text-slate-400 text-sm">Loading…</p>
          ) : modules.length === 0 ? (
            <p className="text-center py-8 text-slate-400 text-sm">No modules yet</p>
          ) : modules.map(mod => (
            <button
              key={mod.id}
              onClick={() => openEdit(mod)}
              className={`w-full text-left px-4 py-3 border-b border-slate-50 hover:bg-slate-50 transition-colors ${
                selected?.id === mod.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-slate-800 leading-snug line-clamp-2">{mod.title_kn}</p>
                <ChevronRight className="w-4 h-4 text-slate-300 shrink-0 mt-0.5" />
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                  mod.published ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                }`}>
                  {mod.published ? 'Published' : 'Draft'}
                </span>
                {mod.category && (
                  <span className="text-xs text-slate-400">{mod.category}</span>
                )}
                <span className="text-xs text-slate-400 ml-auto">{mod.estimated_minutes}m</span>
              </div>
            </button>
          ))}
        </div>

        <div className="px-4 py-2 border-t border-slate-100 text-xs text-slate-400">
          {total} module{total !== 1 ? 's' : ''}
        </div>
      </div>

      {/* ── RIGHT: Editor or Placeholder ──────────────────────── */}
      <div className="flex-1 overflow-y-auto bg-slate-50">
        {!selected && !isNew ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-3">
            <BookOpen className="w-12 h-12 opacity-20" />
            <p className="text-sm">Select a module or create a new one</p>
          </div>
        ) : (
          <div className="max-w-2xl mx-auto p-6 space-y-5">
            {/* Toolbar */}
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-base font-semibold text-slate-800 flex-1 min-w-0">
                {isNew ? 'New Module' : form.title_kn || 'Edit Module'}
              </h2>

              {/* AI Breakdown */}
              <button
                onClick={() => setShowAIPanel(true)}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors"
              >
                <Sparkles className="w-3 h-3" /> AI Breakdown
              </button>

              {/* Progress */}
              {selected && (
                <button
                  onClick={loadProgress}
                  disabled={progressLoading}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 transition-colors"
                >
                  <BarChart2 className="w-3 h-3" />
                  {progressLoading ? 'Loading…' : 'Progress'}
                </button>
              )}

              {/* Publish toggle */}
              {selected && (
                <button
                  onClick={handlePublish}
                  disabled={publishing || !!isEditorDirty}
                  title={isEditorDirty ? 'Save first' : ''}
                  className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors disabled:opacity-50 ${
                    selected.published
                      ? 'border-slate-200 hover:bg-slate-100 text-slate-600'
                      : 'border-green-300 bg-green-50 hover:bg-green-100 text-green-700'
                  }`}
                >
                  {selected.published ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                  {publishing ? '…' : (selected.published ? 'Unpublish' : 'Publish')}
                </button>
              )}

              {/* Send */}
              {selected?.published && (
                <button
                  onClick={handleSend}
                  disabled={sending || !!isEditorDirty}
                  title={isEditorDirty ? 'Save first' : ''}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-50"
                >
                  <Send className="w-3 h-3" />
                  {sending ? 'Sending…' : 'Send to all'}
                </button>
              )}

              {/* Deactivate */}
              {selected && (
                <button
                  onClick={handleDeactivate}
                  className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500 transition-colors"
                  title="Deactivate module"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>

            {sendResult && (
              <div className="bg-green-50 border border-green-200 text-green-800 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
                <span>Sent: {sendResult.succeeded} delivered, {sendResult.failed} failed of {sendResult.attempted}</span>
                <button onClick={() => setSendResult(null)}><X className="w-4 h-4" /></button>
              </div>
            )}

            {/* ─── Form ──────────────────────────────────────── */}
            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Basic Info</h3>

              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">Title (Kannada) *</label>
                <input
                  value={form.title_kn || ''}
                  onChange={f('title_kn')}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="ಮಾಡ್ಯೂಲ್ ಶೀರ್ಷಿಕೆ…"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">Category</label>
                  <select value={form.category || ''} onChange={f('category')}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">Difficulty</label>
                  <select value={form.difficulty || 'beginner'} onChange={f('difficulty')}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                    {DIFFICULTIES.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-slate-600 block mb-1">Est. minutes</label>
                  <input type="number" min={1} max={60}
                    value={form.estimated_minutes || 5}
                    onChange={fNum('estimated_minutes')}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">Sequence order</label>
                <input type="number" min={0}
                  value={form.sequence_order ?? 0}
                  onChange={fNum('sequence_order')}
                  className="w-32 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* ─── Steps ─────────────────────────────────────── */}
            {([1, 2, 3] as const).map(step => {
              const hKey = `step_${['one','two','three'][step-1]}_heading_kn` as keyof Module
              const tKey = `step_${['one','two','three'][step-1]}_text_kn` as keyof Module
              const iKey = `step_${['one','two','three'][step-1]}_image_url` as keyof Module
              return (
                <div key={step} className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
                  <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Step {step}</h3>
                  <div>
                    <label className="text-xs font-medium text-slate-600 block mb-1">Heading (Kannada)</label>
                    <input
                      value={(form[hKey] as string) || ''}
                      onChange={e => setForm(prev => ({ ...prev, [hKey]: e.target.value }))}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder={`ಹಂತ ${step} ಶೀರ್ಷಿಕೆ…`}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600 block mb-1">Content (Kannada)</label>
                    <textarea
                      rows={3}
                      value={(form[tKey] as string) || ''}
                      onChange={e => setForm(prev => ({ ...prev, [tKey]: e.target.value }))}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder={`ಹಂತ ${step} ವಿಷಯ…`}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-slate-600 block mb-1">Image (S3 object key, optional)</label>
                    <input
                      value={(form[iKey] as string) || ''}
                      onChange={e => setForm(prev => ({ ...prev, [iKey]: e.target.value }))}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="learning/module-id/step1/image.jpg"
                    />
                  </div>
                </div>
              )
            })}

            {/* ─── Practice Prompt ───────────────────────────── */}
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Practice Task</h3>
              <textarea
                rows={2}
                value={form.practice_prompt_kn || ''}
                onChange={f('practice_prompt_kn')}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="ಇಂದು ಮಾಡಬೇಕಾದ ಒಂದು ಚಟುವಟಿಕೆ…"
              />
            </div>

            {/* Save */}
            <div className="flex justify-end gap-3 pb-4">
              {(selected || isNew) && (
                <button
                  onClick={handleSave}
                  disabled={saving || !form.title_kn?.trim()}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
                >
                  <CheckCircle className="w-4 h-4" />
                  {saving ? 'Saving…' : (isNew ? 'Create module' : 'Save changes')}
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── AI Breakdown Panel ───────────────────────────────── */}
      {showAIPanel && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-blue-500" />
                <h2 className="font-semibold text-slate-800">AI Breakdown</h2>
              </div>
              <button onClick={() => setShowAIPanel(false)}>
                <X className="w-5 h-5 text-slate-400 hover:text-slate-600" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">Topic hint (optional)</label>
                <input
                  value={aiTopic}
                  onChange={e => setAITopic(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g. how to use a computer mouse"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-600 block mb-1">
                  Paste text to convert <span className="text-red-500">*</span>
                </label>
                <textarea
                  rows={8}
                  value={aiText}
                  onChange={e => setAIText(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Paste PDF content, notes, or instructions here…"
                />
              </div>
              <p className="text-xs text-slate-400">
                Gemini will break this into a 3-step Kannada micro-learning module and pre-fill the editor.
              </p>
            </div>
            <div className="px-6 py-4 border-t border-slate-100 flex justify-end gap-3">
              <button
                onClick={() => setShowAIPanel(false)}
                className="px-4 py-2 text-sm rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-600"
              >
                Cancel
              </button>
              <button
                onClick={handleAIBreakdown}
                disabled={aiLoading || !aiText.trim()}
                className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
              >
                <Sparkles className="w-4 h-4" />
                {aiLoading ? 'Generating…' : 'Generate module'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Progress Panel ───────────────────────────────────── */}
      {showProgress && progress && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <div>
                <h2 className="font-semibold text-slate-800">Module Progress</h2>
                <p className="text-xs text-slate-400 mt-0.5">{progress.module_title}</p>
              </div>
              <button onClick={() => setShowProgress(false)}>
                <X className="w-5 h-5 text-slate-400 hover:text-slate-600" />
              </button>
            </div>
            <div className="p-6">
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4 mb-5">
                {[
                  { label: 'Sent', value: progress.total_sent, color: 'blue' },
                  { label: 'Viewed', value: progress.total_viewed, color: 'purple' },
                  { label: 'Practice done', value: progress.total_practice_completed, color: 'green' },
                ].map(({ label, value, color }) => (
                  <div key={label} className={`rounded-xl p-4 text-center bg-${color}-50 border border-${color}-100`}>
                    <p className={`text-2xl font-bold text-${color}-700`}>{value}</p>
                    <p className={`text-xs text-${color}-500 mt-1`}>{label}</p>
                  </div>
                ))}
              </div>

              {/* Per district */}
              {progress.by_district.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left">
                      <th className="pb-2 font-medium text-slate-500">District</th>
                      <th className="pb-2 font-medium text-slate-500 text-right">Sent</th>
                      <th className="pb-2 font-medium text-slate-500 text-right">Viewed</th>
                      <th className="pb-2 font-medium text-slate-500 text-right">Practice</th>
                      <th className="pb-2 font-medium text-slate-500 text-right">%</th>
                    </tr>
                  </thead>
                  <tbody>
                    {progress.by_district.map(row => (
                      <tr key={row.district} className="border-b border-slate-50">
                        <td className="py-2 text-slate-700">{row.district}</td>
                        <td className="py-2 text-right text-slate-500">{row.sent_count}</td>
                        <td className="py-2 text-right text-slate-500">{row.viewed_count}</td>
                        <td className="py-2 text-right text-slate-500">{row.practice_completed_count}</td>
                        <td className="py-2 text-right font-medium text-slate-700">{row.completion_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-slate-400 text-sm text-center py-4">No data yet — module not sent</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
