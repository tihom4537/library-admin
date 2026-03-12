import { useState, useEffect } from 'react'
import {
  Plus, Wand2, X, Loader2, Trash2, Save, ChevronLeft, ChevronRight,
  Sparkles, CheckSquare, Square, ArrowRight, Info, Calendar,
  BookOpen, Check,
} from 'lucide-react'
import api from '@/lib/api'
import { Badge } from '@/components/Badge'

// ── Types ────────────────────────────────────────────────────────────────────

interface SpecialDay {
  id: string
  month: number
  day: number
  year: number | null
  occasion_kn: string
  occasion_en: string
  is_system: boolean
}

interface Step {
  order: number
  text_kn: string
  text_en?: string
}

interface ActivityDraft {
  title_kn: string
  title_en: string | null
  description_kn: string | null
  category: string | null
  age_group: string
  difficulty: string
  duration_minutes: number | null
  steps_kn: Step[]
  materials_kn: string | null
  is_mandatory: boolean
}

interface Template {
  id: string
  title_kn: string
  title_en: string | null
  category: string | null
  age_group: string | null
  difficulty: string | null
  duration_minutes: number | null
  status: string
  times_used: number
  steps_kn: Step[]
  materials_kn: string | null
  description_kn: string | null
}

// ── Calendar helpers ──────────────────────────────────────────────────────────

const MONTH_NAMES = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December',
]
const DAY_LABELS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']

function buildCalendarGrid(year: number, month: number): (Date | null)[] {
  const first = new Date(year, month - 1, 1)
  const last  = new Date(year, month, 0)
  const cells: (Date | null)[] = []
  for (let i = 0; i < first.getDay(); i++) cells.push(null)
  for (let d = 1; d <= last.getDate(); d++) cells.push(new Date(year, month - 1, d))
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
}

function isoDate(d: Date) { return d.toISOString().slice(0, 10) }
function dayKey(d: Date)  { return `${d.getMonth() + 1}-${d.getDate()}` }
function isToday(d: Date) {
  const t = new Date()
  return d.getDate() === t.getDate() && d.getMonth() === t.getMonth() && d.getFullYear() === t.getFullYear()
}

/** Returns an emoji that matches the occasion for rich calendar display */
function occasionIcon(occasion_en: string): string {
  const o = occasion_en.toLowerCase()
  if (o.includes('republic'))                     return '🇮🇳'
  if (o.includes('independence'))                 return '🇮🇳'
  if (o.includes('martyr') || o.includes('shaheed')) return '🕊️'
  if (o.includes('women'))                        return '🌸'
  if (o.includes('science'))                      return '🔬'
  if (o.includes('autism'))                       return '💙'
  if (o.includes('earth'))                        return '🌍'
  if (o.includes('book'))                         return '📚'
  if (o.includes('labour') || o.includes('labor')) return '⚒️'
  if (o.includes('environment'))                  return '🌿'
  if (o.includes('yoga'))                         return '🧘'
  if (o.includes('population'))                   return '👥'
  if (o.includes('sports'))                       return '🏆'
  if (o.includes('teacher'))                      return '🎓'
  if (o.includes('literacy'))                     return '📖'
  if (o.includes('gandhi'))                       return '🕊️'
  if (o.includes('food'))                         return '🌾'
  if (o.includes('karnataka rajyotsava'))         return '⭐'
  if (o.includes('children'))                     return '🧒'
  if (o.includes('toilet'))                       return '🚿'
  if (o.includes('aids'))                         return '❤️'
  if (o.includes('human rights'))                 return '✊'
  if (o.includes('holika'))                       return '🔥'
  if (o.includes('holi'))                         return '🎨'
  if (o.includes('safety'))                       return '🦺'
  if (o.includes('vaccination'))                  return '💉'
  if (o.includes('ugadi') || o.includes('gudi')) return '🌺'
  if (o.includes('navami') || o.includes('ram navami')) return '🙏'
  if (o.includes('navratri'))                     return '🪔'
  return '⭐'
}

// ── Main component ────────────────────────────────────────────────────────────

export function Activities() {
  const [tab, setTab] = useState<'calendar' | 'templates'>('calendar')

  // ── Calendar tab state ────────────────────────────────────────────────────
  const today = new Date()
  const [calYear, setCalYear]   = useState(today.getFullYear())
  const [calMonth, setCalMonth] = useState(today.getMonth() + 1)
  const [selectedDate, setSelectedDate] = useState<Date | null>(null)
  const [sdMap, setSdMap] = useState<Record<string, SpecialDay[]>>({})

  // Side panel
  const [customOccasion, setCustomOccasion] = useState('')
  const [addingDay, setAddingDay]           = useState(false)
  const [addDayLoading, setAddDayLoading]   = useState(false)
  const [suggestions, setSuggestions]       = useState<ActivityDraft[] | null>(null)
  const [suggestLoading, setSuggestLoading] = useState(false)
  const [selectedIdxs, setSelectedIdxs]     = useState<Set<number>>(new Set())
  const [expandedIdxs, setExpandedIdxs]     = useState<Set<number>>(new Set())

  // Circular creation modal
  const [showCircularModal, setShowCircularModal] = useState(false)
  const [circularNumber, setCircularNumber]       = useState('')
  const [pushLoading, setPushLoading]             = useState(false)
  const [pushResult, setPushResult]               = useState<{ circular_id: string; circular_number: string } | null>(null)

  // ── Template tab state ────────────────────────────────────────────────────
  const [templates, setTemplates]     = useState<Template[]>([])
  const [total, setTotal]             = useState(0)
  const [search, setSearch]           = useState('')
  const [category, setCategory]       = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [tplLoading, setTplLoading]   = useState(false)
  const [editing, setEditing]         = useState<any | null>(null)
  const [saving, setSaving]           = useState(false)
  const [aiLoading, setAiLoading]     = useState(false)

  // ── Effects ───────────────────────────────────────────────────────────────

  useEffect(() => { loadSpecialDays(calYear) }, [calYear])

  useEffect(() => {
    if (tab === 'templates') loadTemplates()
  }, [tab, search, category, statusFilter])

  // ── Data loaders ──────────────────────────────────────────────────────────

  async function loadSpecialDays(year: number) {
    try {
      const r = await api.get(`/activities/special-days?year=${year}`)
      const days: SpecialDay[] = r.data
      const map: Record<string, SpecialDay[]> = {}
      days.forEach(d => {
        const k = `${d.month}-${d.day}`
        if (!map[k]) map[k] = []
        map[k].push(d)
      })
      setSdMap(map)
    } catch { /* non-critical */ }
  }

  async function loadTemplates() {
    setTplLoading(true)
    try {
      const p = new URLSearchParams({ page: '1', page_size: '30' })
      if (search)       p.set('search', search)
      if (category)     p.set('category', category)
      if (statusFilter) p.set('status', statusFilter)
      const r = await api.get(`/activities/templates?${p}`)
      setTemplates(r.data.items)
      setTotal(r.data.total)
    } finally { setTplLoading(false) }
  }

  // ── Calendar handlers ─────────────────────────────────────────────────────

  function prevMonth() {
    if (calMonth === 1) { setCalYear(y => y - 1); setCalMonth(12) }
    else setCalMonth(m => m - 1)
  }
  function nextMonth() {
    if (calMonth === 12) { setCalYear(y => y + 1); setCalMonth(1) }
    else setCalMonth(m => m + 1)
  }

  function handleDateClick(d: Date) {
    setSelectedDate(d)
    setSuggestions(null)
    setSelectedIdxs(new Set())
    setExpandedIdxs(new Set())
    setCustomOccasion('')
    setAddingDay(false)
    setPushResult(null)
  }

  function getOccasions(d: Date): SpecialDay[] {
    return sdMap[dayKey(d)] ?? []
  }

  function getOccasion(d: Date): SpecialDay | null {
    const list = sdMap[dayKey(d)]
    return list?.[0] ?? null
  }

  async function generateSuggestions() {
    if (!selectedDate) return
    const occasion = getOccasion(selectedDate)
    const text = customOccasion.trim() || occasion?.occasion_en || ''
    if (!text) { alert('Please enter an occasion name first.'); return }

    setSuggestLoading(true)
    setSuggestions(null)
    try {
      const r = await api.post('/activities/templates/suggest-for-occasion', {
        occasion: text,
        occasion_date: isoDate(selectedDate),
      })
      setSuggestions((r.data as ActivityDraft[]).map(d => ({ ...d, is_mandatory: true })))
    } catch (e: any) {
      alert('AI suggestion failed: ' + (e.response?.data?.detail ?? e.message))
    } finally { setSuggestLoading(false) }
  }

  function toggleSelect(idx: number) {
    setSelectedIdxs(prev => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
  }

  function toggleExpand(idx: number) {
    setExpandedIdxs(prev => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
  }

  function toggleMandatory(idx: number) {
    setSuggestions(prev =>
      prev?.map((s, i) => i === idx ? { ...s, is_mandatory: !s.is_mandatory } : s) ?? null
    )
  }

  async function addSpecialDay() {
    if (!selectedDate || !customOccasion.trim()) return
    setAddDayLoading(true)
    try {
      await api.post('/activities/special-days', {
        month: selectedDate.getMonth() + 1,
        day: selectedDate.getDate(),
        year: selectedDate.getFullYear(),
        occasion_kn: customOccasion.trim(),
        occasion_en: customOccasion.trim(),
      })
      await loadSpecialDays(calYear)
      setAddingDay(false)
      setCustomOccasion('')
    } catch (e: any) {
      alert('Failed: ' + (e.response?.data?.detail ?? e.message))
    } finally { setAddDayLoading(false) }
  }

  async function saveAsTemplates() {
    if (!suggestions || selectedIdxs.size === 0) return
    try {
      const selected = [...selectedIdxs].map(i => suggestions[i])
      await Promise.all(selected.map(act =>
        api.post('/activities/templates', { ...act, status: 'published' })
      ))
      alert(`${selected.length} template(s) saved to library!`)
      setSelectedIdxs(new Set())
    } catch (e: any) {
      alert('Failed: ' + (e.response?.data?.detail ?? e.message))
    }
  }

  async function createCircular() {
    if (!selectedDate || !suggestions || selectedIdxs.size === 0 || !circularNumber.trim()) return
    const occasion = getOccasion(selectedDate)
    const occasionText = customOccasion.trim() || occasion?.occasion_en || 'Special Occasion'
    setPushLoading(true)
    try {
      const selected = [...selectedIdxs].map(i => suggestions[i])
      const r = await api.post('/activities/push-to-circular', {
        circular_number: circularNumber.trim(),
        issue_date: isoDate(selectedDate),
        occasion: occasionText,
        activities: selected,
      })
      setPushResult(r.data)
      setShowCircularModal(false)
      setCircularNumber('')
      setSelectedIdxs(new Set())
    } catch (e: any) {
      alert('Failed: ' + (e.response?.data?.detail ?? e.message))
    } finally { setPushLoading(false) }
  }

  // ── Template tab handlers ─────────────────────────────────────────────────

  async function saveTemplate() {
    if (!editing) return
    setSaving(true)
    try {
      if (editing.id) {
        await api.put(`/activities/templates/${editing.id}`, editing)
      } else {
        await api.post('/activities/templates', editing)
      }
      setEditing(null)
      loadTemplates()
    } catch (e: any) {
      alert(e.response?.data?.detail ?? 'Save failed')
    } finally { setSaving(false) }
  }

  async function archiveTemplate(id: string) {
    if (!confirm('Archive this template?')) return
    await api.delete(`/activities/templates/${id}`)
    loadTemplates()
  }

  async function aiSuggestTemplate() {
    if (!editing) return
    setAiLoading(true)
    try {
      const r = await api.post('/activities/templates/ai-suggest', {
        category: editing.category || 'reading',
        age_group: editing.age_group || 'all',
        recent_titles: templates.slice(0, 5).map((t: Template) => t.title_en ?? t.title_kn),
      })
      const d = r.data
      setEditing((prev: any) => ({
        ...prev,
        title_kn: d.title_kn ?? prev.title_kn,
        title_en: d.title_en ?? prev.title_en,
        description_kn: d.description_kn ?? prev.description_kn,
        materials_kn: d.materials_kn ?? prev.materials_kn,
        duration_minutes: d.duration_minutes ?? prev.duration_minutes,
        difficulty: d.difficulty ?? prev.difficulty,
        steps_kn: d.steps ?? [],
      }))
    } catch { alert('AI suggestion failed') }
    finally { setAiLoading(false) }
  }

  function addStep() {
    setEditing((prev: any) => ({
      ...prev,
      steps_kn: [...prev.steps_kn, { order: prev.steps_kn.length + 1, text_kn: '', text_en: '' }],
    }))
  }

  function updateStep(idx: number, field: string, val: string) {
    setEditing((prev: any) => {
      const steps = [...prev.steps_kn]
      steps[idx] = { ...steps[idx], [field]: val }
      return { ...prev, steps_kn: steps }
    })
  }

  function removeStep(idx: number) {
    setEditing((prev: any) => ({
      ...prev,
      steps_kn: prev.steps_kn
        .filter((_: any, i: number) => i !== idx)
        .map((s: any, i: number) => ({ ...s, order: i + 1 })),
    }))
  }

  // ── Template editor (shown as full page when editing !== null) ─────────────
  if (editing !== null && tab === 'templates') {
    return (
      <div className="p-6 max-w-2xl space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-800">
            {editing.id ? 'Edit Template' : 'New Template'}
          </h1>
          <button onClick={() => setEditing(null)} className="text-slate-400 hover:text-slate-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="bg-white rounded-xl border shadow-sm p-5 space-y-4">
          <button
            onClick={aiSuggestTemplate}
            disabled={aiLoading}
            className="flex items-center gap-2 text-sm text-purple-700 bg-purple-50 hover:bg-purple-100 border border-purple-200 px-3 py-2 rounded-lg transition-colors w-full justify-center"
          >
            {aiLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
            {aiLoading ? 'Generating…' : 'AI Suggest (fill form with Gemini)'}
          </button>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Title (Kannada) *">
              <input value={editing.title_kn} onChange={e => setEditing((p: any) => ({ ...p, title_kn: e.target.value }))} className="input-base" />
            </Field>
            <Field label="Title (English)">
              <input value={editing.title_en ?? ''} onChange={e => setEditing((p: any) => ({ ...p, title_en: e.target.value }))} className="input-base" />
            </Field>
          </div>

          <Field label="Description (Kannada)">
            <textarea rows={2} value={editing.description_kn ?? ''} onChange={e => setEditing((p: any) => ({ ...p, description_kn: e.target.value }))} className="input-base" />
          </Field>

          <div className="grid grid-cols-3 gap-3">
            <Field label="Category">
              <select value={editing.category ?? ''} onChange={e => setEditing((p: any) => ({ ...p, category: e.target.value }))} className="input-base">
                {['reading','art','science','craft','story','digital','outdoor'].map(c => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Age Group">
              <select value={editing.age_group ?? ''} onChange={e => setEditing((p: any) => ({ ...p, age_group: e.target.value }))} className="input-base">
                {['all','5-8','8-12','12+'].map(c => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Difficulty">
              <select value={editing.difficulty ?? ''} onChange={e => setEditing((p: any) => ({ ...p, difficulty: e.target.value }))} className="input-base">
                {['easy','medium','hard'].map(c => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Duration (min)">
              <input type="number" value={editing.duration_minutes ?? ''} onChange={e => setEditing((p: any) => ({ ...p, duration_minutes: +e.target.value }))} className="input-base" />
            </Field>
            <Field label="Status">
              <select value={editing.status} onChange={e => setEditing((p: any) => ({ ...p, status: e.target.value }))} className="input-base">
                <option value="published">Published</option>
                <option value="draft">Draft</option>
              </select>
            </Field>
          </div>

          <Field label="Materials (Kannada)">
            <textarea rows={2} value={editing.materials_kn ?? ''} onChange={e => setEditing((p: any) => ({ ...p, materials_kn: e.target.value }))} className="input-base" />
          </Field>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-slate-700">Steps</label>
              <button onClick={addStep} className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1">
                <Plus className="w-3 h-3" /> Add step
              </button>
            </div>
            {editing.steps_kn.length === 0 && (
              <p className="text-xs text-slate-400 text-center py-4 border rounded-lg border-dashed">No steps yet</p>
            )}
            <div className="space-y-2">
              {editing.steps_kn.map((step: any, i: number) => (
                <div key={i} className="flex gap-2 items-start">
                  <span className="text-xs text-slate-400 mt-2.5 w-5 shrink-0">{i + 1}.</span>
                  <div className="flex-1 space-y-1">
                    <input value={step.text_kn} onChange={e => updateStep(i, 'text_kn', e.target.value)} placeholder="Step (Kannada)" className="input-base" />
                    <input value={step.text_en ?? ''} onChange={e => updateStep(i, 'text_en', e.target.value)} placeholder="Step (English, optional)" className="input-base text-xs" />
                  </div>
                  <button onClick={() => removeStep(i)} className="mt-2 text-slate-400 hover:text-red-500"><X className="w-4 h-4" /></button>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-3">
          <button onClick={() => setEditing(null)} className="flex-1 border rounded-lg py-2.5 text-sm text-slate-600 hover:bg-slate-50">Cancel</button>
          <button onClick={saveTemplate} disabled={saving || !editing.title_kn}
            className="flex-1 bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? 'Saving…' : 'Save Template'}
          </button>
        </div>
        <style>{`.input-base{width:100%;border:1px solid #e2e8f0;border-radius:.5rem;padding:.5rem .75rem;font-size:.875rem;outline:none}.input-base:focus{border-color:#3b82f6;box-shadow:0 0 0 2px rgba(59,130,246,.15)}`}</style>
      </div>
    )
  }

  // ── Calendar grid ──────────────────────────────────────────────────────────
  const calGrid = buildCalendarGrid(calYear, calMonth)
  const occasion = selectedDate ? getOccasion(selectedDate) : null
  const selectedOccasions = selectedDate ? getOccasions(selectedDate) : []
  const occasionText = customOccasion.trim() || occasion?.occasion_en || ''
  const specialDaysThisMonth = Object.values(sdMap).flat().filter(d => d.month === calMonth)

  // ── Main render ────────────────────────────────────────────────────────────
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Tabs */}
      <div className="shrink-0 px-6 pt-4 pb-0 bg-white border-b flex gap-1 items-end">
        <h1 className="text-xl font-bold text-slate-800 mr-6 pb-3">Activities</h1>
        {(['calendar', 'templates'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            {t === 'calendar'
              ? <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4" />Calendar</span>
              : <span className="flex items-center gap-1.5"><BookOpen className="w-4 h-4" />Template Library</span>
            }
          </button>
        ))}
      </div>

      {/* ── CALENDAR TAB ─────────────────────────────────────────────────── */}
      {tab === 'calendar' && (
        <div className="flex-1 flex overflow-hidden">
          {/* Left: Calendar */}
          <div className={`flex flex-col shrink-0 transition-all ${selectedDate ? 'w-[500px]' : 'flex-1'} overflow-y-auto p-6`}>
            {/* Month nav */}
            <div className="flex items-center justify-between mb-4">
              <button onClick={prevMonth} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-600">
                <ChevronLeft className="w-5 h-5" />
              </button>
              <div className="text-center">
                <span className="text-lg font-bold text-slate-800">{MONTH_NAMES[calMonth - 1]} {calYear}</span>
                <div className="text-xs text-slate-400 mt-0.5">{specialDaysThisMonth.length} special days this month</div>
              </div>
              <button onClick={nextMonth} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-600">
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>

            {/* Day headers */}
            <div className="grid grid-cols-7 mb-1">
              {DAY_LABELS.map(l => (
                <div key={l} className="text-center text-xs font-medium text-slate-400 py-1">{l}</div>
              ))}
            </div>

            {/* Calendar grid */}
            <div className="grid grid-cols-7 gap-1">
              {calGrid.map((d, i) => {
                if (!d) return <div key={i} className="min-h-[80px]" />
                const occasions = sdMap[dayKey(d)] ?? []
                const primary = occasions[0] ?? null
                const isSelected = selectedDate?.toDateString() === d.toDateString()
                const todayCell = isToday(d)
                // Pick icons for up to 2 occasions
                const icons = occasions.slice(0, 2).map(o => occasionIcon(o.occasion_en))
                return (
                  <button
                    key={i}
                    onClick={() => handleDateClick(d)}
                    title={occasions.map(o => o.occasion_en).join(' · ') || undefined}
                    className={`relative flex flex-col items-center justify-start pt-1.5 pb-1.5 px-0.5 rounded-xl text-sm transition-all min-h-[80px] group ${
                      isSelected
                        ? 'bg-blue-600 text-white shadow-lg ring-2 ring-blue-300'
                        : primary
                        ? 'bg-gradient-to-b from-amber-50 to-orange-50 hover:from-amber-100 hover:to-orange-100 border border-orange-200 shadow-sm'
                        : todayCell
                        ? 'bg-blue-50 hover:bg-blue-100 border border-blue-200'
                        : 'hover:bg-slate-50 border border-transparent hover:border-slate-200'
                    }`}
                  >
                    {/* Emoji icons — up to 2 for multi-occasion days */}
                    {icons.length > 0 && (
                      <span className="leading-none mb-0.5 transition-transform group-hover:scale-110 flex gap-0.5">
                        {icons.map((ic, ii) => (
                          <span key={ii} className="text-[18px]">{ic}</span>
                        ))}
                      </span>
                    )}
                    {/* Date number */}
                    <span className={`font-bold leading-none text-sm ${
                      isSelected ? 'text-white' :
                      todayCell ? 'text-blue-600' :
                      primary ? 'text-orange-700' : 'text-slate-700'
                    }`}>
                      {d.getDate()}
                    </span>
                    {/* Primary occasion name (truncated) */}
                    {primary && (
                      <span className={`text-[7.5px] leading-tight mt-0.5 text-center line-clamp-2 px-0.5 font-medium ${
                        isSelected ? 'text-white/90' : 'text-orange-600'
                      }`}>
                        {primary.occasion_en.split('/')[0].trim()}
                        {occasions.length > 1 && <span className="opacity-60"> +{occasions.length - 1}</span>}
                      </span>
                    )}
                    {/* Today dot */}
                    {todayCell && !isSelected && (
                      <span className="absolute bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-blue-500" />
                    )}
                  </button>
                )
              })}
            </div>

            {/* Legend */}
            <div className="flex gap-5 mt-4 text-xs text-slate-400 flex-wrap">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-gradient-to-b from-amber-50 to-orange-100 border border-orange-200 inline-block" />
                Special / Festival day
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded bg-blue-100 border border-blue-200 inline-block" />
                Today
              </span>
            </div>

            {/* Tip when nothing selected */}
            {!selectedDate && (
              <div className="mt-6 text-center text-slate-400 text-sm">
                <p>Click any date to generate AI activity suggestions</p>
                <p className="text-xs mt-1">Orange highlights = pre-loaded special days</p>
              </div>
            )}
          </div>

          {/* Right: Side panel */}
          {selectedDate && (
            <div className="flex-1 border-l bg-slate-50 overflow-y-auto flex flex-col min-w-0">
              {/* Panel header */}
              <div className="sticky top-0 bg-white border-b px-5 py-4 flex items-start justify-between z-10">
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide font-medium">
                    {selectedDate.toLocaleDateString('en-IN', { weekday: 'long' })}
                  </p>
                  <h2 className="text-lg font-bold text-slate-800">
                    {selectedDate.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}
                  </h2>
                  {selectedOccasions.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {selectedOccasions.map((occ, oi) => (
                        <div key={oi} className="flex items-center gap-1 bg-orange-50 border border-orange-200 rounded-full px-2 py-0.5 text-orange-700 text-xs font-medium">
                          <span>{occasionIcon(occ.occasion_en)}</span>
                          <span>{occ.occasion_en}</span>
                          {occ.is_system && <span className="text-orange-400 text-[10px]">·system</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <button onClick={() => setSelectedDate(null)} className="text-slate-400 hover:text-slate-700 mt-1">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-5 space-y-4">
                {/* Add occasion section */}
                {!addingDay && !occasion && (
                  <button
                    onClick={() => setAddingDay(true)}
                    className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
                  >
                    <Plus className="w-4 h-4" /> Mark as special day
                  </button>
                )}

                {(addingDay || occasion) && (
                  <div className="bg-white rounded-xl border p-4 space-y-3">
                    <label className="text-xs font-medium text-slate-600">
                      {occasion ? 'Use a different occasion (optional)' : 'Occasion name'}
                    </label>
                    <input
                      value={customOccasion}
                      onChange={e => setCustomOccasion(e.target.value)}
                      placeholder={occasion ? `${occasion.occasion_en} (leave blank to use this)` : 'e.g. School Annual Day'}
                      className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    {addingDay && !occasion && (
                      <button
                        onClick={addSpecialDay}
                        disabled={!customOccasion.trim() || addDayLoading}
                        className="text-xs bg-orange-100 text-orange-700 border border-orange-200 px-3 py-1.5 rounded-lg hover:bg-orange-200 disabled:opacity-50 transition-colors"
                      >
                        {addDayLoading ? 'Saving…' : 'Save to calendar'}
                      </button>
                    )}
                  </div>
                )}

                {/* Generate button */}
                <button
                  onClick={generateSuggestions}
                  disabled={suggestLoading || !occasionText}
                  className="w-full flex items-center justify-center gap-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-xl py-3 text-sm font-medium transition-colors"
                >
                  {suggestLoading
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating activities…</>
                    : <><Sparkles className="w-4 h-4" /> Generate AI Activities{occasionText ? ` for "${occasionText}"` : ''}</>
                  }
                </button>

                {/* Success banner */}
                {pushResult && (
                  <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-start gap-3">
                    <Check className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-green-800">Circular #{pushResult.circular_number} created!</p>
                      <p className="text-xs text-green-600 mt-0.5">Go to Circulars to review and send to librarians.</p>
                    </div>
                  </div>
                )}

                {/* Suggestion cards */}
                {suggestions && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-slate-700">{suggestions.length} suggestions</p>
                      <div className="flex gap-3 text-xs">
                        <button onClick={() => setSelectedIdxs(new Set(suggestions.map((_, i) => i)))} className="text-blue-600 hover:text-blue-800">Select all</button>
                        <button onClick={() => setSelectedIdxs(new Set())} className="text-slate-500 hover:text-slate-700">Clear</button>
                      </div>
                    </div>

                    {suggestions.map((act, idx) => {
                      const sel = selectedIdxs.has(idx)
                      const exp = expandedIdxs.has(idx)
                      return (
                        <div key={idx} className={`bg-white rounded-xl border-2 transition-all ${sel ? 'border-blue-400 shadow-sm' : 'border-slate-200'}`}>
                          <div className="p-4">
                            <div className="flex items-start gap-3">
                              <button onClick={() => toggleSelect(idx)} className="mt-0.5 shrink-0">
                                {sel
                                  ? <CheckSquare className="w-5 h-5 text-blue-600" />
                                  : <Square className="w-5 h-5 text-slate-400" />
                                }
                              </button>
                              <div className="flex-1 min-w-0">
                                <p className="font-semibold text-slate-800 text-sm leading-tight">{act.title_kn}</p>
                                {act.title_en && <p className="text-xs text-slate-500 mt-0.5">{act.title_en}</p>}
                                <div className="flex flex-wrap gap-1.5 mt-2">
                                  {act.category && <Badge label={act.category} />}
                                  {act.age_group && <Badge label={act.age_group} />}
                                  {act.difficulty && <Badge label={act.difficulty} />}
                                  {act.duration_minutes && <span className="text-xs text-slate-400">{act.duration_minutes}min</span>}
                                </div>
                                {act.description_kn && (
                                  <p className="text-xs text-slate-600 mt-2 leading-relaxed">{act.description_kn}</p>
                                )}
                              </div>
                            </div>

                            {/* Controls row */}
                            <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
                              {sel ? (
                                <button
                                  onClick={() => toggleMandatory(idx)}
                                  className={`text-xs px-2.5 py-1 rounded-full border font-medium transition-colors ${
                                    act.is_mandatory
                                      ? 'bg-red-50 text-red-700 border-red-200'
                                      : 'bg-slate-50 text-slate-600 border-slate-200'
                                  }`}
                                >
                                  {act.is_mandatory ? '⭐ Mandatory' : 'Optional'}
                                </button>
                              ) : <div />}
                              <button
                                onClick={() => toggleExpand(idx)}
                                className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                              >
                                <Info className="w-3 h-3" />
                                {exp ? 'Hide steps' : 'View steps'}
                              </button>
                            </div>

                            {/* Expanded steps */}
                            {exp && act.steps_kn.length > 0 && (
                              <div className="mt-3 space-y-2 border-t pt-3">
                                {act.steps_kn.map((s, si) => (
                                  <div key={si} className="flex gap-2 text-xs">
                                    <span className="shrink-0 text-slate-400 font-medium w-4">{s.order}.</span>
                                    <div>
                                      <p className="text-slate-700">{s.text_kn}</p>
                                      {s.text_en && <p className="text-slate-400 mt-0.5">{s.text_en}</p>}
                                    </div>
                                  </div>
                                ))}
                                {act.materials_kn && (
                                  <p className="text-xs text-slate-500 mt-2 pt-2 border-t">
                                    <span className="font-medium">Materials:</span> {act.materials_kn}
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })}

                    {/* Action buttons */}
                    {selectedIdxs.size > 0 && (
                      <div className="flex gap-2 pt-2 sticky bottom-4">
                        <button
                          onClick={saveAsTemplates}
                          className="flex-1 border border-blue-300 text-blue-700 text-sm font-medium py-2.5 rounded-xl hover:bg-blue-50 bg-white shadow-sm transition-colors"
                        >
                          Save Templates ({selectedIdxs.size})
                        </button>
                        <button
                          onClick={() => setShowCircularModal(true)}
                          className="flex-1 bg-blue-600 text-white text-sm font-medium py-2.5 rounded-xl hover:bg-blue-700 shadow-sm transition-colors flex items-center justify-center gap-2"
                        >
                          <ArrowRight className="w-4 h-4" />
                          Create Circular ({selectedIdxs.size})
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TEMPLATES TAB ────────────────────────────────────────────────── */}
      {tab === 'templates' && (
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Manage reusable activity templates</span>
            <button
              onClick={() => setEditing({ title_kn: '', title_en: '', category: 'reading', age_group: 'all', difficulty: 'easy', duration_minutes: 30, status: 'published', materials_kn: '', description_kn: '', steps_kn: [] })}
              className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700"
            >
              <Plus className="w-4 h-4" /> New Template
            </button>
          </div>

          {/* Filters */}
          <div className="bg-white rounded-xl border shadow-sm p-4 flex gap-3 flex-wrap">
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search…" className="input-base flex-1 min-w-40" />
            <select value={category} onChange={e => setCategory(e.target.value)} className="input-base">
              <option value="">All categories</option>
              {['reading','art','science','craft','story','digital','outdoor'].map(c => <option key={c}>{c}</option>)}
            </select>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="input-base">
              <option value="">Published + Draft</option>
              <option value="published">Published</option>
              <option value="draft">Draft</option>
              <option value="archived">Archived</option>
            </select>
            <span className="text-sm text-slate-500 self-center ml-auto">{total} templates</span>
          </div>

          {/* Template grid */}
          {tplLoading ? (
            <div className="text-center py-16 text-slate-400">Loading…</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {templates.map(t => (
                <div key={t.id} className="bg-white rounded-xl border shadow-sm p-4 hover:border-blue-300 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-slate-800 text-sm leading-tight">{t.title_kn}</p>
                      {t.title_en && <p className="text-xs text-slate-500 mt-0.5">{t.title_en}</p>}
                    </div>
                    <Badge label={t.status} status={t.status} />
                  </div>
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    {t.category && <Badge label={t.category} />}
                    {t.age_group && <Badge label={t.age_group} />}
                    {t.difficulty && <Badge label={t.difficulty} />}
                  </div>
                  <div className="flex items-center justify-between mt-3 text-xs text-slate-400">
                    <span>{t.duration_minutes ? `${t.duration_minutes} min` : ''}</span>
                    <span>{t.times_used} reports</span>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <button onClick={() => setEditing({ ...t })} className="flex-1 text-xs border rounded-lg py-1.5 text-slate-600 hover:bg-slate-50">Edit</button>
                    <button onClick={() => archiveTemplate(t.id)} className="p-1.5 border rounded-lg text-slate-400 hover:text-red-500 hover:border-red-300">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))}
              {templates.length === 0 && (
                <div className="col-span-3 text-center py-16 text-slate-400">
                  <p>No templates yet.</p>
                  <p className="text-xs mt-1">Use the Calendar tab to generate and save activities, or click New Template.</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Create Circular Modal ──────────────────────────────────────────── */}
      {showCircularModal && selectedDate && suggestions && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-800 text-lg">Create Circular</h3>
              <button onClick={() => setShowCircularModal(false)} className="text-slate-400 hover:text-slate-700">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-slate-500">
              Saves {selectedIdxs.size} activit{selectedIdxs.size > 1 ? 'ies' : 'y'} as templates and creates a draft circular ready to send.
            </p>

            {/* Activity summary */}
            <div className="bg-slate-50 rounded-xl p-3 space-y-1.5 max-h-40 overflow-y-auto">
              {[...selectedIdxs].map(i => suggestions[i]).map((act, j) => (
                <div key={j} className="flex items-center gap-2 text-xs">
                  <span className={`px-1.5 py-0.5 rounded font-medium shrink-0 ${act.is_mandatory ? 'bg-red-100 text-red-700' : 'bg-slate-200 text-slate-600'}`}>
                    {act.is_mandatory ? 'Mandatory' : 'Optional'}
                  </span>
                  <span className="truncate text-slate-700">{act.title_kn}</span>
                </div>
              ))}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Circular Number *</label>
              <input
                value={circularNumber}
                onChange={e => setCircularNumber(e.target.value)}
                placeholder="e.g. DSERT/2026/03"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex gap-3 pt-1">
              <button onClick={() => setShowCircularModal(false)} className="flex-1 border rounded-lg py-2.5 text-sm text-slate-600 hover:bg-slate-50">
                Cancel
              </button>
              <button
                onClick={createCircular}
                disabled={pushLoading || !circularNumber.trim()}
                className="flex-1 bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {pushLoading
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating…</>
                  : <><ArrowRight className="w-4 h-4" /> Create Circular</>
                }
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`.input-base{width:100%;border:1px solid #e2e8f0;border-radius:.5rem;padding:.5rem .75rem;font-size:.875rem;outline:none}.input-base:focus{border-color:#3b82f6;box-shadow:0 0 0 2px rgba(59,130,246,.15)}`}</style>
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
