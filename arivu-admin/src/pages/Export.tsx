import { useState } from 'react'
import { Download, Users, ClipboardList, BarChart2, CheckCircle } from 'lucide-react'
import api from '@/lib/api'

interface ExportJob {
  id: string
  label: string
  description: string
  icon: typeof Download
  endpoint: string
  params?: Record<string, string>
  filename: string
}

function useDownload() {
  const [loading, setLoading] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const download = async (job: ExportJob, extraParams?: Record<string, string>) => {
    setLoading(job.id)
    setDone(null)
    try {
      const response = await api.get(job.endpoint, {
        params: { ...job.params, ...extraParams },
        responseType: 'blob',
      })
      const blob = new Blob([response.data], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = job.filename
      a.click()
      URL.revokeObjectURL(url)
      setDone(job.id)
      setTimeout(() => setDone(null), 3000)
    } catch {
      alert('Export failed')
    } finally {
      setLoading(null)
    }
  }

  return { loading, done, download }
}

export function Export() {
  const { loading, done, download } = useDownload()

  // Report filters
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [district, setDistrict] = useState('')
  const [libStatus, setLibStatus] = useState('')

  const jobs: ExportJob[] = [
    {
      id: 'librarians',
      label: 'Librarians',
      description: 'All librarian profiles — name, district, status, last active date',
      icon: Users,
      endpoint: '/export/librarians',
      filename: `librarians_${new Date().toISOString().slice(0, 10)}.csv`,
    },
    {
      id: 'reports',
      label: 'Activity Reports',
      description: 'All submitted activity reports with optional date and district filters',
      icon: ClipboardList,
      endpoint: '/export/reports',
      filename: `activity_reports_${new Date().toISOString().slice(0, 10)}.csv`,
    },
    {
      id: 'compliance',
      label: 'Compliance Summary',
      description: 'Mandatory activity compliance per district per scheduled activity',
      icon: BarChart2,
      endpoint: '/export/compliance',
      filename: `compliance_${new Date().toISOString().slice(0, 10)}.csv`,
    },
  ]

  const handleDownload = (job: ExportJob) => {
    const extra: Record<string, string> = {}
    if (job.id === 'reports') {
      if (fromDate) extra.from_date = fromDate
      if (toDate) extra.to_date = toDate
      if (district) extra.district = district
    }
    if (job.id === 'librarians' && libStatus) {
      extra.status = libStatus
    }
    download(job, extra)
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Export Data</h1>
        <p className="text-slate-500 text-sm mt-1">Download portal data as CSV files for offline analysis</p>
      </div>

      <div className="space-y-4">
        {jobs.map(job => {
          const Icon = job.icon
          const isLoading = loading === job.id
          const isDone = done === job.id

          return (
            <div key={job.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start gap-4">
                <div className="p-2.5 rounded-xl bg-blue-50 shrink-0">
                  <Icon className="w-5 h-5 text-blue-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-slate-800">{job.label}</h3>
                  <p className="text-sm text-slate-500 mt-0.5">{job.description}</p>

                  {/* Filters for specific jobs */}
                  {job.id === 'librarians' && (
                    <div className="mt-3 flex gap-3 flex-wrap">
                      <select
                        value={libStatus}
                        onChange={e => setLibStatus(e.target.value)}
                        className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">All statuses</option>
                        <option value="onboarded">Onboarded</option>
                        <option value="pending">Pending</option>
                        <option value="inactive">Inactive</option>
                      </select>
                    </div>
                  )}

                  {job.id === 'reports' && (
                    <div className="mt-3 flex gap-3 flex-wrap">
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">From date</label>
                        <input
                          type="date"
                          value={fromDate}
                          onChange={e => setFromDate(e.target.value)}
                          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">To date</label>
                        <input
                          type="date"
                          value={toDate}
                          onChange={e => setToDate(e.target.value)}
                          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 block mb-1">District</label>
                        <input
                          value={district}
                          onChange={e => setDistrict(e.target.value)}
                          placeholder="e.g. Belagavi"
                          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                      </div>
                    </div>
                  )}
                </div>

                <button
                  onClick={() => handleDownload(job)}
                  disabled={isLoading}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors disabled:opacity-60 shrink-0 ${
                    isDone
                      ? 'bg-green-100 text-green-700 border border-green-200'
                      : 'bg-blue-600 hover:bg-blue-700 text-white'
                  }`}
                >
                  {isDone
                    ? <><CheckCircle className="w-4 h-4" /> Downloaded</>
                    : isLoading
                    ? <><div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" /> Exporting…</>
                    : <><Download className="w-4 h-4" /> Download CSV</>
                  }
                </button>
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-xs text-slate-400 mt-6 text-center">
        Files are encoded with UTF-8 BOM for correct display in Excel/LibreOffice
      </p>
    </div>
  )
}
