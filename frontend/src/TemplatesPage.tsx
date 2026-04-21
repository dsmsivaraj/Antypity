import { useEffect, useState } from 'react'
import { api } from './api'
import type { ResumeTemplate } from './types'

const STYLE_OPTIONS = ['', 'minimal', 'modern', 'executive', 'academic', 'creative']

export function TemplatesPage() {
  const [templates, setTemplates] = useState<ResumeTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [styleFilter, setStyleFilter] = useState('')
  const [selected, setSelected] = useState<ResumeTemplate | null>(null)

  // Design new template
  const [designing, setDesigning] = useState(false)
  const [designForm, setDesignForm] = useState({ name: '', target_role: '', style: 'modern', notes: '' })
  const [designLoading, setDesignLoading] = useState(false)
  const [designError, setDesignError] = useState('')

  useEffect(() => {
    api.getResumeTemplates()
      .then(r => setTemplates(r.templates))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = styleFilter
    ? templates.filter(t => t.style.toLowerCase() === styleFilter)
    : templates

  async function handleDesign() {
    if (!designForm.name.trim() || !designForm.target_role.trim()) return
    setDesignLoading(true)
    setDesignError('')
    try {
      const t = await api.designResumeTemplate(designForm)
      setTemplates(prev => [t, ...prev])
      setSelected(t)
      setDesigning(false)
      setDesignForm({ name: '', target_role: '', style: 'modern', notes: '' })
    } catch (e) {
      setDesignError(e instanceof Error ? e.message : 'Design failed')
    } finally {
      setDesignLoading(false)
    }
  }

  return (
    <div className="row g-4">
      <div className="col-12 d-flex justify-content-between align-items-center">
        <div>
          <div className="text-uppercase small text-secondary fw-semibold">Resume</div>
          <h2 className="section-title h4 mb-0">Templates</h2>
        </div>
        <div className="d-flex gap-2 align-items-center">
          <select
            className="form-select form-select-sm"
            style={{ width: 160 }}
            value={styleFilter}
            onChange={e => setStyleFilter(e.target.value)}
          >
            <option value="">All styles</option>
            {STYLE_OPTIONS.filter(Boolean).map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
          <button className="btn btn-primary btn-sm" onClick={() => setDesigning(d => !d)}>
            {designing ? 'Cancel' : '+ Design New'}
          </button>
        </div>
      </div>

      {designing && (
        <div className="col-12">
          <div className="card glass-card border-0 rounded-4">
            <div className="card-body p-4">
              <h5 className="mb-3">Design a New Template via AI</h5>
              <div className="row g-3">
                <div className="col-md-4">
                  <label className="form-label small fw-semibold">Template Name</label>
                  <input
                    className="form-control form-control-sm"
                    placeholder="e.g. Senior Engineer 2025"
                    value={designForm.name}
                    onChange={e => setDesignForm(f => ({ ...f, name: e.target.value }))}
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label small fw-semibold">Target Role</label>
                  <input
                    className="form-control form-control-sm"
                    placeholder="e.g. Staff Software Engineer"
                    value={designForm.target_role}
                    onChange={e => setDesignForm(f => ({ ...f, target_role: e.target.value }))}
                  />
                </div>
                <div className="col-md-4">
                  <label className="form-label small fw-semibold">Style</label>
                  <select
                    className="form-select form-select-sm"
                    value={designForm.style}
                    onChange={e => setDesignForm(f => ({ ...f, style: e.target.value }))}
                  >
                    {STYLE_OPTIONS.filter(Boolean).map(s => (
                      <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                    ))}
                  </select>
                </div>
                <div className="col-12">
                  <label className="form-label small fw-semibold">Notes (optional)</label>
                  <textarea
                    className="form-control form-control-sm"
                    rows={2}
                    placeholder="Any specific requirements, sections, or design preferences…"
                    value={designForm.notes}
                    onChange={e => setDesignForm(f => ({ ...f, notes: e.target.value }))}
                  />
                </div>
              </div>
              {designError && <div className="alert alert-danger mt-3 py-2 small">{designError}</div>}
              <button
                className="btn btn-primary mt-3"
                onClick={handleDesign}
                disabled={designLoading || !designForm.name.trim() || !designForm.target_role.trim()}
              >
                {designLoading ? 'Generating…' : 'Generate Template'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="col-lg-4">
        <div className="card glass-card border-0 rounded-4 h-100">
          <div className="card-body p-3">
            {loading && <div className="text-center py-4 text-secondary">Loading templates…</div>}
            {error && <div className="alert alert-danger py-2 small">{error}</div>}
            {!loading && filtered.length === 0 && (
              <div className="text-center py-4 text-secondary">No templates found.</div>
            )}
            <div className="d-flex flex-column gap-2">
              {filtered.map(t => (
                <button
                  key={t.id}
                  type="button"
                  className={`btn text-start border rounded-3 p-3 ${selected?.id === t.id ? 'btn-primary' : 'btn-light'}`}
                  onClick={() => setSelected(t)}
                >
                  <div className="fw-semibold">{t.name}</div>
                  <div className="small text-truncate">{t.target_role}</div>
                  <div className="d-flex gap-1 mt-1 flex-wrap">
                    <span className={`badge ${selected?.id === t.id ? 'bg-light text-primary' : 'bg-secondary bg-opacity-10 text-secondary'}`}>
                      {t.style}
                    </span>
                    <span className={`badge ${selected?.id === t.id ? 'bg-light text-primary' : 'soft-badge'}`}>
                      {t.source}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="col-lg-8">
        {selected ? (
          <div className="card glass-card border-0 rounded-4">
            <div className="card-body p-4">
              <div className="d-flex justify-content-between align-items-start mb-3">
                <div>
                  <h4 className="section-title mb-1">{selected.name}</h4>
                  <div className="text-secondary small">{selected.target_role} &middot; {selected.style}</div>
                </div>
                <div className="d-flex gap-2">
                  <span className="badge bg-secondary">{selected.source}</span>
                </div>
              </div>

              {selected.sections.length > 0 && (
                <div className="mb-3">
                  <div className="text-uppercase small text-secondary fw-semibold mb-2">Sections</div>
                  <div className="d-flex flex-wrap gap-2">
                    {selected.sections.map((s, i) => (
                      <span key={i} className="badge soft-badge">{s}</span>
                    ))}
                  </div>
                </div>
              )}

              {Object.keys(selected.design_tokens).length > 0 && (
                <div className="mb-3">
                  <div className="text-uppercase small text-secondary fw-semibold mb-2">Design Tokens</div>
                  <div className="row g-2">
                    {Object.entries(selected.design_tokens).map(([k, v]) => (
                      <div key={k} className="col-auto">
                        <div className="border rounded-2 px-2 py-1 small d-flex align-items-center gap-2">
                          {k.toLowerCase().includes('color') && (
                            <span
                              className="rounded-circle d-inline-block"
                              style={{ width: 12, height: 12, background: v, border: '1px solid #ccc' }}
                            />
                          )}
                          <span className="text-secondary">{k}:</span>
                          <span className="fw-mono">{v}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selected.figma_prompt && (
                <div className="mb-3">
                  <div className="text-uppercase small text-secondary fw-semibold mb-2">Figma Prompt</div>
                  <div className="bg-light rounded-3 p-3 small">{selected.figma_prompt}</div>
                </div>
              )}

              {selected.preview_markdown && (
                <div>
                  <div className="text-uppercase small text-secondary fw-semibold mb-2">Preview</div>
                  <pre className="code-block bg-light rounded-3 p-3 small">{selected.preview_markdown}</pre>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="card glass-card border-0 rounded-4 h-100 d-flex align-items-center justify-content-center">
            <div className="text-center text-secondary py-5">
              <div className="fs-1 mb-2">📄</div>
              <div>Select a template to preview details</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
