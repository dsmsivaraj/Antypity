import { useEffect, useState } from 'react'
import { api } from './api'
import type { JobSearchResult, JobSource } from './types'

export function JobsPage() {
  const [sources, setSources] = useState<JobSource[]>([])
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [keywords, setKeywords] = useState('')
  const [locations, setLocations] = useState('')
  const [jdText, setJdText] = useState('')
  const [results, setResults] = useState<JobSearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sourcesLoaded, setSourcesLoaded] = useState(false)

  // JD extraction
  const [jdUrl, setJdUrl] = useState('')
  const [jdLoading, setJdLoading] = useState(false)
  const [extractedJd, setExtractedJd] = useState<{ title: string; company: string; keywords: string[] } | null>(null)

  useEffect(() => {
    api.getJobSources()
      .then(r => {
        setSources(r.sources)
        setSelectedSources(r.sources.map(s => s.id))
      })
      .catch(() => {})
      .finally(() => setSourcesLoaded(true))
  }, [])

  function toggleSource(id: string) {
    setSelectedSources(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  async function handleSearch() {
    const kws = keywords.split(',').map(s => s.trim()).filter(Boolean)
    if (kws.length === 0) return
    const locs = locations.split(',').map(s => s.trim()).filter(Boolean)
    setLoading(true)
    setError('')
    try {
      const res = await api.searchJobs({ keywords: kws, locations: locs, sources: selectedSources })
      setResults(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleExtractJd() {
    if (!jdUrl.trim() && !jdText.trim()) return
    setJdLoading(true)
    try {
      const jd = await api.extractJobDescription({ url: jdUrl || undefined, text: jdText || undefined })
      setExtractedJd({ title: jd.title, company: jd.company, keywords: jd.keywords })
      if (jd.keywords.length > 0) {
        setKeywords(jd.keywords.slice(0, 6).join(', '))
      }
    } catch {
      // ignore
    } finally {
      setJdLoading(false)
    }
  }

  return (
    <div className="row g-4">
      <div className="col-12">
        <div className="text-uppercase small text-secondary fw-semibold">Career</div>
        <h2 className="section-title h4 mb-0">Job Search</h2>
      </div>

      {/* Search controls */}
      <div className="col-lg-4">
        <div className="card glass-card border-0 rounded-4 mb-4">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold mb-3">Search</div>
            <div className="mb-3">
              <label className="form-label small fw-semibold">Keywords</label>
              <input
                className="form-control form-control-sm"
                placeholder="e.g. React, TypeScript, remote"
                value={keywords}
                onChange={e => setKeywords(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
              />
              <div className="form-text">Comma-separated</div>
            </div>
            <div className="mb-3">
              <label className="form-label small fw-semibold">Locations (optional)</label>
              <input
                className="form-control form-control-sm"
                placeholder="e.g. San Francisco, Remote"
                value={locations}
                onChange={e => setLocations(e.target.value)}
              />
            </div>
            <button
              className="btn btn-primary w-100"
              onClick={handleSearch}
              disabled={loading || !keywords.trim()}
            >
              {loading ? 'Searching…' : 'Search Jobs'}
            </button>
          </div>
        </div>

        <div className="card glass-card border-0 rounded-4 mb-4">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold mb-3">Job Portals</div>
            {!sourcesLoaded && <div className="text-secondary small">Loading…</div>}
            <div className="d-flex flex-column gap-2">
              {sources.map(s => (
                <div key={s.id} className="form-check">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    id={`src-${s.id}`}
                    checked={selectedSources.includes(s.id)}
                    onChange={() => toggleSource(s.id)}
                  />
                  <label className="form-check-label small" htmlFor={`src-${s.id}`}>
                    {s.label}
                  </label>
                </div>
              ))}
            </div>
            <div className="d-flex gap-2 mt-3">
              <button className="btn btn-sm btn-outline-secondary" onClick={() => setSelectedSources(sources.map(s => s.id))}>All</button>
              <button className="btn btn-sm btn-outline-secondary" onClick={() => setSelectedSources([])}>None</button>
            </div>
          </div>
        </div>

        <div className="card glass-card border-0 rounded-4">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold mb-3">Extract from JD</div>
            <div className="mb-2">
              <input
                className="form-control form-control-sm mb-2"
                placeholder="Job posting URL (optional)"
                value={jdUrl}
                onChange={e => setJdUrl(e.target.value)}
              />
              <textarea
                className="form-control form-control-sm"
                rows={3}
                placeholder="Or paste job description text…"
                value={jdText}
                onChange={e => setJdText(e.target.value)}
              />
            </div>
            <button
              className="btn btn-sm btn-outline-primary w-100"
              onClick={handleExtractJd}
              disabled={jdLoading || (!jdUrl.trim() && !jdText.trim())}
            >
              {jdLoading ? 'Extracting…' : 'Extract Keywords'}
            </button>
            {extractedJd && (
              <div className="mt-3 p-2 bg-light rounded-3 small">
                <div className="fw-semibold">{extractedJd.title} @ {extractedJd.company}</div>
                <div className="d-flex flex-wrap gap-1 mt-1">
                  {extractedJd.keywords.map((k, i) => (
                    <span key={i} className="badge soft-badge">{k}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="col-lg-8">
        <div className="card glass-card border-0 rounded-4 h-100">
          <div className="card-body p-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <div className="text-uppercase small text-secondary fw-semibold">Results</div>
              {results.length > 0 && (
                <span className="badge bg-secondary">{results.length} jobs</span>
              )}
            </div>

            {error && <div className="alert alert-danger py-2 small">{error}</div>}

            {results.length === 0 && !loading && (
              <div className="text-center text-secondary py-5">
                <div className="fs-1 mb-2">🔍</div>
                <div>Enter keywords and click Search to find jobs across multiple portals.</div>
                <div className="small mt-2 text-muted">Results include direct links to job postings on LinkedIn, Indeed, Glassdoor, and more.</div>
              </div>
            )}

            {loading && (
              <div className="text-center text-secondary py-5">
                <div className="spinner-border spinner-border-sm me-2" role="status" />
                Searching job portals…
              </div>
            )}

            <div className="d-flex flex-column gap-3">
              {results.map(job => (
                <div key={job.id} className="border rounded-3 p-3 bg-white">
                  <div className="d-flex justify-content-between align-items-start">
                    <div>
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="fw-semibold text-decoration-none"
                      >
                        {job.title}
                      </a>
                      <div className="small text-secondary">{job.company} &middot; {job.location}</div>
                    </div>
                    <div className="d-flex gap-2 align-items-center">
                      {job.ats_score != null && (
                        <span className={`badge ${job.ats_score >= 70 ? 'bg-success' : job.ats_score >= 40 ? 'bg-warning text-dark' : 'bg-secondary'}`}>
                          ATS {job.ats_score}%
                        </span>
                      )}
                      <span className="badge soft-badge">{job.source}</span>
                    </div>
                  </div>
                  {job.summary && (
                    <div className="small text-secondary mt-2">{job.summary}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
