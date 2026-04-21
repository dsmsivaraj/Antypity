import { useState, useRef } from 'react'
import { api } from './api'
import type {
  JobHuntResponse,
  JobOpportunity,
  LiveJobHuntResponse,
  LiveJobResult,
  ResumeEvaluationResponse,
  ResumeReviewResponse,
  ResumeWriteResponse,
} from './types'

type SkillTab = 'live' | 'hunt' | 'evaluate' | 'write' | 'review'

const TIER_COLOR: Record<string, string> = {
  high: '#16a34a',
  medium: '#d97706',
  stretch: '#7c3aed',
}

const TIER_BG: Record<string, string> = {
  high: '#f0fdf4',
  medium: '#fffbeb',
  stretch: '#f5f3ff',
}

function ScoreBar({ score, max = 100 }: { score: number; max?: number }) {
  const pct = Math.round((score / max) * 100)
  const color = pct >= 70 ? '#16a34a' : pct >= 45 ? '#d97706' : '#ef4444'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, background: '#e5e7eb', borderRadius: 4, height: 8 }}>
        <div style={{ width: `${pct}%`, background: color, borderRadius: 4, height: 8, transition: 'width .4s' }} />
      </div>
      <span style={{ fontSize: 13, fontWeight: 700, color, minWidth: 40 }}>{score}/{max}</span>
    </div>
  )
}

function JobCard({ job, rank }: { job: JobOpportunity; rank?: number }) {
  const tierColor = TIER_COLOR[job.tier] || '#6b7280'
  const tierBg = TIER_BG[job.tier] || '#f9fafb'
  return (
    <div style={{
      border: `1px solid ${tierColor}30`,
      borderLeft: `4px solid ${tierColor}`,
      borderRadius: 10,
      padding: '14px 16px',
      background: tierBg,
      marginBottom: 10,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            {rank && <span style={{ background: '#1e40af', color: '#fff', borderRadius: 12, padding: '1px 8px', fontSize: 11, fontWeight: 700 }}>#{rank}</span>}
            <span style={{ fontWeight: 700, fontSize: 15 }}>{job.company}</span>
            <span style={{
              background: tierColor + '20',
              color: tierColor,
              border: `1px solid ${tierColor}`,
              borderRadius: 12,
              padding: '1px 8px',
              fontSize: 11,
              fontWeight: 700,
              textTransform: 'uppercase',
            }}>{job.tier}</span>
          </div>
          <div style={{ color: '#374151', fontSize: 13, marginBottom: 4 }}>
            <strong>{job.role}</strong> &nbsp;·&nbsp; {job.company_type} &nbsp;·&nbsp; {job.location}
          </div>
          <div style={{ color: '#6b7280', fontSize: 12 }}>
            {job.sector.replace(/_/g, ' ')} &nbsp;·&nbsp; ₹{job.package_lpa} LPA
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, minWidth: 110 }}>
          <div style={{ fontWeight: 700, fontSize: 20, color: tierColor }}>{job.fit_score}<span style={{ fontSize: 12, fontWeight: 400, color: '#6b7280' }}>/100</span></div>
          <a
            href={job.apply_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              background: tierColor,
              color: '#fff',
              borderRadius: 6,
              padding: '6px 14px',
              fontWeight: 600,
              fontSize: 13,
              textDecoration: 'none',
              whiteSpace: 'nowrap',
            }}
          >Apply Now →</a>
        </div>
      </div>
    </div>
  )
}

const SOURCE_COLOR: Record<string, string> = {
  indeed: '#2164f3',
  remotive: '#00b186',
  linkedin: '#0a66c2',
  naukri: '#ef5a23',
}

function LiveJobCard({ job, expanded, onToggle }: { job: LiveJobResult; expanded: boolean; onToggle: () => void }) {
  const tierColor = TIER_COLOR[job.tier] || '#6b7280'
  const tierBg = TIER_BG[job.tier] || '#f9fafb'
  const srcColor = SOURCE_COLOR[job.source] || '#6b7280'
  const pct = job.match_score
  const barColor = pct >= 60 ? '#16a34a' : pct >= 35 ? '#d97706' : '#ef4444'

  return (
    <div style={{ border: `1px solid ${tierColor}30`, borderLeft: `4px solid ${tierColor}`, borderRadius: 10, background: tierBg, marginBottom: 10, overflow: 'hidden' }}>
      <div onClick={onToggle} style={{ padding: '12px 16px', cursor: 'pointer' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
              <span style={{ background: srcColor + '18', color: srcColor, border: `1px solid ${srcColor}40`, borderRadius: 10, padding: '1px 8px', fontSize: 11, fontWeight: 700 }}>{job.source_label}</span>
              <span style={{ background: tierColor + '18', color: tierColor, border: `1px solid ${tierColor}`, borderRadius: 10, padding: '1px 8px', fontSize: 11, fontWeight: 700, textTransform: 'uppercase' as const }}>{job.tier}</span>
            </div>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 2, whiteSpace: 'nowrap' as const, overflow: 'hidden', textOverflow: 'ellipsis' }}>{job.title}</div>
            <div style={{ fontSize: 13, color: '#374151' }}>{job.company} &nbsp;·&nbsp; {job.location}</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' as const, alignItems: 'flex-end', gap: 4, minWidth: 110 }}>
            <div style={{ fontWeight: 800, fontSize: 22, color: barColor, lineHeight: 1 }}>{job.match_score}<span style={{ fontSize: 11, fontWeight: 400, color: '#6b7280' }}>%</span></div>
            <div style={{ fontSize: 11, color: '#6b7280' }}>ATS match</div>
            <span style={{ fontSize: 14, color: '#6b7280' }}>{expanded ? '▲' : '▼'}</span>
          </div>
        </div>

        {/* ATS bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
          <div style={{ flex: 1, background: '#e5e7eb', borderRadius: 4, height: 6 }}>
            <div style={{ width: `${pct}%`, background: barColor, borderRadius: 4, height: 6, transition: 'width .4s' }} />
          </div>
          <span style={{ fontSize: 11, color: '#6b7280', minWidth: 120 }}>{job.ats_summary.split(' — ')[0]}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ padding: '0 16px 14px', borderTop: '1px solid #e5e7eb' }}>
          {/* ATS summary */}
          <p style={{ fontSize: 13, color: '#374151', margin: '12px 0 10px', fontStyle: 'italic' }}>{job.ats_summary}</p>

          {/* Keywords */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
            <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: 10 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#15803d', marginBottom: 6 }}>Matched Keywords ({job.matched_keywords.length})</div>
              <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 4 }}>
                {job.matched_keywords.slice(0, 12).map(k => (
                  <span key={k} style={{ background: '#dcfce7', color: '#166534', borderRadius: 8, padding: '1px 7px', fontSize: 11 }}>{k}</span>
                ))}
                {job.matched_keywords.length > 12 && <span style={{ fontSize: 11, color: '#6b7280' }}>+{job.matched_keywords.length - 12} more</span>}
              </div>
            </div>
            <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: 10 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#c2410c', marginBottom: 6 }}>Missing Keywords ({job.missing_keywords.length})</div>
              <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 4 }}>
                {job.missing_keywords.slice(0, 10).map(k => (
                  <span key={k} style={{ background: '#ffedd5', color: '#9a3412', borderRadius: 8, padding: '1px 7px', fontSize: 11 }}>{k}</span>
                ))}
                {job.missing_keywords.length > 10 && <span style={{ fontSize: 11, color: '#6b7280' }}>+{job.missing_keywords.length - 10} more</span>}
              </div>
            </div>
          </div>

          {/* Improvement areas */}
          {job.improvement_areas.length > 0 && (
            <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: 10, marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#dc2626', marginBottom: 6 }}>Areas of Improvement</div>
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: '#b91c1c' }}>
                {job.improvement_areas.map((a, i) => <li key={i} style={{ marginBottom: 3 }}>{a}</li>)}
              </ul>
            </div>
          )}

          {/* JD snippet */}
          {job.jd_snippet && (
            <div style={{ background: '#f8fafc', border: '1px solid #e5e7eb', borderRadius: 8, padding: 10, marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#374151', marginBottom: 4 }}>Job Description Snippet</div>
              <p style={{ margin: 0, fontSize: 12, color: '#6b7280', lineHeight: 1.6 }}>{job.jd_snippet.slice(0, 400)}{job.jd_snippet.length > 400 ? '…' : ''}</p>
            </div>
          )}

          {/* Apply button */}
          {job.url && (
            <a href={job.url} target="_blank" rel="noopener noreferrer"
              style={{ display: 'inline-block', background: tierColor, color: '#fff', borderRadius: 7, padding: '7px 20px', fontWeight: 700, fontSize: 13, textDecoration: 'none' }}>
              Apply Now →
            </a>
          )}
        </div>
      )}
    </div>
  )
}

export function JobHuntPage({ resumeText: initialResumeText }: { resumeText?: string }) {
  const [tab, setTab] = useState<SkillTab>('live')
  const [resumeText, setResumeText] = useState(initialResumeText || '')
  const [jdText, setJdText] = useState('')
  const [targetRole, setTargetRole] = useState('Software Engineer')
  const [location, setLocation] = useState('India')
  const [experienceYears, setExperienceYears] = useState('0')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Results
  const [liveResult, setLiveResult] = useState<LiveJobHuntResponse | null>(null)
  const [huntResult, setHuntResult] = useState<JobHuntResponse | null>(null)
  const [evalResult, setEvalResult] = useState<ResumeEvaluationResponse | null>(null)
  const [writeResult, setWriteResult] = useState<ResumeWriteResponse | null>(null)
  const [reviewResult, setReviewResult] = useState<ResumeReviewResponse | null>(null)

  const [tierFilter, setTierFilter] = useState<'all' | 'high' | 'medium' | 'stretch'>('all')
  const [liveTierFilter, setLiveTierFilter] = useState<'all' | 'high' | 'medium' | 'stretch'>('all')
  const [expandedJob, setExpandedJob] = useState<string | null>(null)
  const [expandedTailored, setExpandedTailored] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFileUpload = async (file: File) => {
    setLoading(true)
    setError('')
    try {
      const parsed = await api.parseResume(file)
      setResumeText(parsed.text)
    } catch (e: unknown) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const runLiveHunt = async () => {
    if (!resumeText) { setError('Upload or paste your resume first.'); return }
    setLoading(true); setError(''); setLiveResult(null)
    try {
      const result = await api.liveHuntJobs({
        resume_text: resumeText,
        location,
        experience_years: parseFloat(experienceYears) || 0,
      })
      setLiveResult(result)
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  const runHunt = async () => {
    if (!resumeText) { setError('Upload or paste your resume first.'); return }
    setLoading(true); setError(''); setHuntResult(null)
    try {
      const result = await api.huntJobs({
        resume_text: resumeText,
        location,
        experience_years: parseFloat(experienceYears) || 0,
        top_count: 30,
      })
      setHuntResult(result)
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  const runEvaluate = async () => {
    if (!resumeText) { setError('Paste your resume first.'); return }
    setLoading(true); setError(''); setEvalResult(null)
    try {
      setEvalResult(await api.evaluateResume(resumeText, jdText))
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  const runWrite = async () => {
    setLoading(true); setError(''); setWriteResult(null)
    try {
      setWriteResult(await api.writeResume({ resume_text: resumeText, jd_text: jdText, target_role: targetRole }))
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  const runReview = async () => {
    if (!resumeText) { setError('Paste your resume first.'); return }
    setLoading(true); setError(''); setReviewResult(null)
    try {
      setReviewResult(await api.reviewResume(resumeText, jdText, targetRole))
    } catch (e: unknown) { setError((e as Error).message) }
    finally { setLoading(false) }
  }

  const filteredOpps = huntResult?.opportunities.filter(
    o => tierFilter === 'all' || o.tier === tierFilter
  ) ?? []

  const liveListings = liveResult?.jobs.filter(j => j.result_type === 'listing' && (liveTierFilter === 'all' || j.tier === liveTierFilter)) ?? []
  const livePortalLinks = liveResult?.jobs.filter(j => j.result_type === 'portal_search') ?? []

  const tabs: { key: SkillTab; label: string; icon: string }[] = [
    { key: 'live', label: 'Live Jobs', icon: '🌐' },
    { key: 'hunt', label: 'AI Job Hunt', icon: '🎯' },
    { key: 'evaluate', label: 'Evaluate', icon: '📊' },
    { key: 'write', label: 'Write', icon: '✍️' },
    { key: 'review', label: 'Review', icon: '🔍' },
  ]

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '0 16px' }}>
      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 24, borderBottom: '2px solid #e5e7eb', paddingBottom: 0 }}>
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: '10px 20px',
              border: 'none',
              borderBottom: tab === t.key ? '3px solid #2563eb' : '3px solid transparent',
              background: 'none',
              cursor: 'pointer',
              fontWeight: tab === t.key ? 700 : 500,
              color: tab === t.key ? '#2563eb' : '#6b7280',
              fontSize: 14,
              marginBottom: -2,
            }}
          >{t.icon} {t.label}</button>
        ))}
      </div>

      {/* Shared: Resume input */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 8 }}>
          <strong style={{ fontSize: 14 }}>Your Resume</strong>
          <button
            onClick={() => fileRef.current?.click()}
            style={{ padding: '5px 14px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}
          >Upload PDF / DOCX</button>
          {resumeText && <span style={{ color: '#16a34a', fontSize: 13 }}>✓ {resumeText.length.toLocaleString()} chars loaded</span>}
        </div>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" style={{ display: 'none' }}
          onChange={e => e.target.files?.[0] && handleFileUpload(e.target.files[0])} />
        <textarea
          value={resumeText}
          onChange={e => setResumeText(e.target.value)}
          placeholder="Or paste your resume text here…"
          rows={5}
          style={{ width: '100%', padding: 10, border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13, fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box' }}
        />
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', color: '#b91c1c', fontSize: 13, marginBottom: 16 }}>{error}</div>}

      {/* ── Live Jobs Tab ───────────────────────────────────────────────── */}
      {tab === 'live' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: 2, minWidth: 140 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 4 }}>Location</label>
              <input value={location} onChange={e => setLocation(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' as const }} />
            </div>
            <div style={{ flex: 1, minWidth: 120 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 4 }}>Experience (years)</label>
              <input type="number" min="0" max="40" value={experienceYears} onChange={e => setExperienceYears(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' as const }} />
            </div>
            <button onClick={runLiveHunt} disabled={loading}
              style={{ padding: '9px 28px', background: '#0f766e', color: '#fff', border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 14, opacity: loading ? 0.7 : 1 }}>
              {loading ? 'Searching portals…' : '🌐 Search Live Jobs'}
            </button>
          </div>

          {loading && (
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#6b7280' }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>Scanning Indeed, Remotive and more…</div>
              <div style={{ fontSize: 13, marginTop: 6 }}>Fetching real job listings and analysing ATS fit for your resume</div>
            </div>
          )}

          {liveResult && (
            <div>
              {/* Header */}
              <div style={{ background: 'linear-gradient(135deg,#134e4a,#0f766e)', color: '#fff', borderRadius: 12, padding: '18px 22px', marginBottom: 20 }}>
                <h2 style={{ margin: '0 0 6px', fontSize: 20 }}>Live Job Results — {liveResult.candidate_name}</h2>
                <div style={{ fontSize: 13, opacity: 0.9, marginBottom: 10 }}>
                  Target Roles: <strong>{liveResult.target_roles.slice(0, 3).join(', ')}</strong>
                </div>
                <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' as const }}>
                  {[
                    { label: 'Total', value: liveResult.total_found, color: '#fff' },
                    { label: 'HIGH', value: liveResult.high_tier.length, color: '#86efac' },
                    { label: 'MEDIUM', value: liveResult.medium_tier.length, color: '#fcd34d' },
                    { label: 'STRETCH', value: liveResult.stretch_tier.length, color: '#c4b5fd' },
                  ].map(s => (
                    <div key={s.label} style={{ background: 'rgba(255,255,255,0.15)', borderRadius: 8, padding: '6px 16px', textAlign: 'center' as const }}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.value}</div>
                      <div style={{ fontSize: 11, opacity: 0.8 }}>{s.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Tier filter */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' as const }}>
                <strong style={{ fontSize: 14 }}>Jobs ({liveResult.total_found})</strong>
                {(['all', 'high', 'medium', 'stretch'] as const).map(t => (
                  <button key={t} onClick={() => setLiveTierFilter(t)}
                    style={{
                      padding: '4px 12px', border: '1px solid', borderRadius: 16, cursor: 'pointer', fontSize: 12, fontWeight: 600,
                      background: liveTierFilter === t ? (TIER_COLOR[t] || '#0f766e') : '#fff',
                      color: liveTierFilter === t ? '#fff' : (TIER_COLOR[t] || '#374151'),
                      borderColor: TIER_COLOR[t] || '#0f766e',
                    }}>
                    {t === 'all' ? `All (${liveResult.total_found})` : `${t.charAt(0).toUpperCase() + t.slice(1)} (${liveResult[`${t}_tier` as 'high_tier'|'medium_tier'|'stretch_tier'].length})`}
                  </button>
                ))}
              </div>

              {/* Live job listings (Remotive etc.) */}
              <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 10px', color: '#0f766e' }}>
                Live Job Listings ({liveListings.length})
              </h3>
              {liveListings.length === 0 && (
                <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: '12px 16px', marginBottom: 18, fontSize: 13, color: '#166534' }}>
                  No remote listings matched this tier filter. Check India Portal Searches below for Naukri/LinkedIn results.
                </div>
              )}
              {liveListings.map(job => (
                <LiveJobCard
                  key={job.id}
                  job={job}
                  expanded={expandedJob === job.id}
                  onToggle={() => setExpandedJob(expandedJob === job.id ? null : job.id)}
                />
              ))}

              {/* India portal search links */}
              {livePortalLinks.length > 0 && (
                <div style={{ marginTop: 24 }}>
                  <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 12px', color: '#1d4ed8' }}>
                    India Portal Searches — {liveResult!.target_roles[0]} & more
                  </h3>
                  <p style={{ fontSize: 12, color: '#6b7280', margin: '0 0 12px' }}>
                    Deep-search links to Naukri, LinkedIn, Indeed, Wellfound — filtered for your seniority and location.
                  </p>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    {livePortalLinks.map(job => {
                      const srcColor = SOURCE_COLOR[job.source] || '#6b7280'
                      return (
                        <div key={job.id} style={{ border: `1px solid ${srcColor}30`, borderLeft: `4px solid ${srcColor}`, borderRadius: 8, padding: 14, background: '#fafafa' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                            <div style={{ flex: 1 }}>
                              <span style={{ background: srcColor + '18', color: srcColor, border: `1px solid ${srcColor}40`, borderRadius: 10, padding: '1px 8px', fontSize: 11, fontWeight: 700 }}>{job.source_label}</span>
                              <div style={{ fontWeight: 700, fontSize: 13, marginTop: 6, marginBottom: 4 }}>{job.title}</div>
                              <p style={{ margin: 0, fontSize: 12, color: '#6b7280', lineHeight: 1.5 }}>{job.jd_snippet}</p>
                            </div>
                          </div>
                          <a href={job.url} target="_blank" rel="noopener noreferrer"
                            style={{ display: 'inline-block', marginTop: 10, background: srcColor, color: '#fff', borderRadius: 6, padding: '5px 14px', fontWeight: 700, fontSize: 12, textDecoration: 'none' }}>
                            Open Search →
                          </a>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── AI Job Hunt Tab ─────────────────────────────────────────────── */}
      {tab === 'hunt' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 140 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 4 }}>Location</label>
              <input value={location} onChange={e => setLocation(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }} />
            </div>
            <div style={{ flex: 1, minWidth: 140 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 4 }}>Experience (years)</label>
              <input type="number" min="0" max="10" value={experienceYears} onChange={e => setExperienceYears(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button onClick={runHunt} disabled={loading}
                style={{ padding: '8px 24px', background: '#1d4ed8', color: '#fff', border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 14, opacity: loading ? 0.7 : 1 }}>
                {loading ? 'Hunting…' : '🎯 Hunt Jobs'}
              </button>
            </div>
          </div>

          {huntResult && (
            <div>
              {/* Header summary */}
              <div style={{ background: 'linear-gradient(135deg,#1e3a8a,#1d4ed8)', color: '#fff', borderRadius: 12, padding: '20px 24px', marginBottom: 20 }}>
                <h2 style={{ margin: '0 0 8px', fontSize: 22 }}>AI Recruiter Report — {huntResult.candidate_name}</h2>
                <div style={{ fontSize: 14, opacity: 0.9, marginBottom: 12 }}>
                  Target Roles: <strong>{huntResult.target_roles.slice(0, 4).join(', ')}</strong>
                </div>
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                  {[
                    { label: 'Total', value: huntResult.total_opportunities, color: '#fff' },
                    { label: 'HIGH', value: huntResult.high_tier.length, color: '#86efac' },
                    { label: 'MEDIUM', value: huntResult.medium_tier.length, color: '#fcd34d' },
                    { label: 'STRETCH', value: huntResult.stretch_tier.length, color: '#c4b5fd' },
                  ].map(s => (
                    <div key={s.label} style={{ background: 'rgba(255,255,255,0.15)', borderRadius: 8, padding: '8px 16px', minWidth: 80, textAlign: 'center' }}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: s.color }}>{s.value}</div>
                      <div style={{ fontSize: 11, opacity: 0.8 }}>{s.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Tailored applications */}
              {huntResult.tailored_applications.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>✍️ Tailored Applications (Top {huntResult.tailored_applications.length})</h3>
                  {huntResult.tailored_applications.map(ta => (
                    <div key={ta.company} style={{ border: '1px solid #e5e7eb', borderRadius: 10, marginBottom: 10, overflow: 'hidden' }}>
                      <div
                        onClick={() => setExpandedTailored(expandedTailored === ta.company ? null : ta.company)}
                        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', cursor: 'pointer', background: '#f8faff' }}
                      >
                        <div>
                          <strong>{ta.company}</strong> — {ta.role}
                          <span style={{ marginLeft: 8, background: '#2563eb20', color: '#2563eb', borderRadius: 10, padding: '1px 8px', fontSize: 11, fontWeight: 700 }}>{ta.fit_score}/100</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <a href={ta.apply_url} target="_blank" rel="noopener noreferrer"
                            onClick={e => e.stopPropagation()}
                            style={{ background: '#2563eb', color: '#fff', borderRadius: 6, padding: '4px 12px', fontSize: 12, fontWeight: 600, textDecoration: 'none' }}>Apply</a>
                          <span style={{ fontSize: 16 }}>{expandedTailored === ta.company ? '▲' : '▼'}</span>
                        </div>
                      </div>
                      {expandedTailored === ta.company && ta.tailored_content && (
                        <div style={{ padding: '14px 16px', borderTop: '1px solid #e5e7eb', fontSize: 13 }}>
                          {ta.tailored_content.tailored_summary && (
                            <div style={{ marginBottom: 12 }}>
                              <strong style={{ color: '#374151' }}>Tailored Summary:</strong>
                              <p style={{ margin: '4px 0 0', color: '#4b5563', lineHeight: 1.6 }}>{ta.tailored_content.tailored_summary}</p>
                            </div>
                          )}
                          {ta.tailored_content.rewritten_bullets && ta.tailored_content.rewritten_bullets.length > 0 && (
                            <div style={{ marginBottom: 12 }}>
                              <strong style={{ color: '#374151' }}>Tailored Bullets:</strong>
                              <ul style={{ margin: '4px 0 0', paddingLeft: 18, color: '#4b5563' }}>
                                {ta.tailored_content.rewritten_bullets.map((b, i) => <li key={i} style={{ marginBottom: 4 }}>{b}</li>)}
                              </ul>
                            </div>
                          )}
                          {ta.tailored_content.cover_line && (
                            <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 6, padding: '8px 12px' }}>
                              <strong style={{ color: '#0369a1' }}>Cover Line: </strong>
                              <span style={{ color: '#0c4a6e' }}>{ta.tailored_content.cover_line}</span>
                            </div>
                          )}
                          {ta.tailored_content.skills_to_add && ta.tailored_content.skills_to_add.length > 0 && (
                            <div style={{ marginTop: 10 }}>
                              <strong style={{ color: '#374151' }}>Add to Skills: </strong>
                              {ta.tailored_content.skills_to_add.map(s => (
                                <span key={s} style={{ background: '#fef3c7', color: '#92400e', borderRadius: 10, padding: '1px 8px', fontSize: 11, marginRight: 4 }}>{s}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Opportunity list */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' }}>
                <strong style={{ fontSize: 14 }}>All Opportunities ({huntResult.total_opportunities})</strong>
                {(['all', 'high', 'medium', 'stretch'] as const).map(t => (
                  <button key={t} onClick={() => setTierFilter(t)}
                    style={{
                      padding: '4px 12px', border: '1px solid', borderRadius: 16, cursor: 'pointer', fontSize: 12, fontWeight: 600,
                      background: tierFilter === t ? (TIER_COLOR[t] || '#1d4ed8') : '#fff',
                      color: tierFilter === t ? '#fff' : (TIER_COLOR[t] || '#374151'),
                      borderColor: TIER_COLOR[t] || '#1d4ed8',
                    }}>{t === 'all' ? `All (${huntResult.total_opportunities})` : `${t.charAt(0).toUpperCase() + t.slice(1)} (${huntResult[`${t}_tier` as 'high_tier'|'medium_tier'|'stretch_tier']?.length ?? 0})`}</button>
                ))}
              </div>
              {filteredOpps.map((job, i) => <JobCard key={job.id} job={job} rank={i + 1} />)}
            </div>
          )}
        </div>
      )}

      {/* ── Evaluate Tab ────────────────────────────────────────────────── */}
      {tab === 'evaluate' && (
        <div>
          <textarea value={jdText} onChange={e => setJdText(e.target.value)}
            placeholder="Paste a job description (optional — for JD-specific ATS scoring)…"
            rows={4}
            style={{ width: '100%', padding: 10, border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13, fontFamily: 'inherit', resize: 'vertical', marginBottom: 12, boxSizing: 'border-box' }} />
          <button onClick={runEvaluate} disabled={loading}
            style={{ padding: '9px 24px', background: '#7c3aed', color: '#fff', border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 14, opacity: loading ? 0.7 : 1 }}>
            {loading ? 'Evaluating…' : '📊 Evaluate Resume'}
          </button>

          {evalResult && (
            <div style={{ marginTop: 20 }}>
              <div style={{ display: 'flex', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
                <div style={{ background: evalResult.overall_score >= 70 ? '#f0fdf4' : evalResult.overall_score >= 45 ? '#fffbeb' : '#fef2f2', borderRadius: 12, padding: '16px 24px', textAlign: 'center', border: '2px solid #e5e7eb', minWidth: 120 }}>
                  <div style={{ fontSize: 40, fontWeight: 800, color: evalResult.overall_score >= 70 ? '#16a34a' : evalResult.overall_score >= 45 ? '#d97706' : '#ef4444' }}>{evalResult.overall_score}</div>
                  <div style={{ fontSize: 12, color: '#6b7280' }}>Overall Score</div>
                  <div style={{ fontSize: 22, fontWeight: 700 }}>Grade {evalResult.grade}</div>
                </div>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, marginBottom: 8 }}>{evalResult.summary}</div>
                  <span style={{
                    background: evalResult.ats_risk_level === 'low' ? '#dcfce7' : evalResult.ats_risk_level === 'medium' ? '#fef9c3' : '#fee2e2',
                    color: evalResult.ats_risk_level === 'low' ? '#166534' : evalResult.ats_risk_level === 'medium' ? '#854d0e' : '#991b1b',
                    borderRadius: 8, padding: '3px 12px', fontSize: 12, fontWeight: 700,
                  }}>ATS Risk: {evalResult.ats_risk_level.toUpperCase()}</span>
                </div>
              </div>

              {Object.keys(evalResult.dimensions).length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>Dimension Breakdown</h4>
                  {Object.entries(evalResult.dimensions).map(([key, dim]) => (
                    <div key={key} style={{ marginBottom: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                        <span style={{ fontWeight: 600 }}>{key.replace(/_/g, ' ')}</span>
                        <span style={{ color: '#6b7280' }}>{dim.notes}</span>
                      </div>
                      <ScoreBar score={dim.score} max={dim.max} />
                    </div>
                  ))}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: 14 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#15803d', margin: '0 0 8px' }}>✓ Strengths</h4>
                  <ul style={{ margin: 0, paddingLeft: 16, fontSize: 13, color: '#166534' }}>
                    {evalResult.top_strengths.map((s, i) => <li key={i} style={{ marginBottom: 4 }}>{s}</li>)}
                  </ul>
                </div>
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: 14 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#dc2626', margin: '0 0 8px' }}>⚠ Critical Fixes</h4>
                  <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#b91c1c' }}>
                    {evalResult.critical_fixes.map((f, i) => <li key={i} style={{ marginBottom: 4 }}>{f}</li>)}
                  </ol>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Write Tab ────────────────────────────────────────────────────── */}
      {tab === 'write' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 4 }}>Target Role</label>
              <input value={targetRole} onChange={e => setTargetRole(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }} />
            </div>
          </div>
          <textarea value={jdText} onChange={e => setJdText(e.target.value)}
            placeholder="Paste a job description to align keywords (optional)…"
            rows={4}
            style={{ width: '100%', padding: 10, border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13, fontFamily: 'inherit', resize: 'vertical', marginBottom: 12, boxSizing: 'border-box' }} />
          <button onClick={runWrite} disabled={loading}
            style={{ padding: '9px 24px', background: '#0284c7', color: '#fff', border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 14, opacity: loading ? 0.7 : 1 }}>
            {loading ? 'Writing…' : '✍️ Generate Resume Content'}
          </button>

          {writeResult && (
            <div style={{ marginTop: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>Generated Content for: {writeResult.target_role}</h3>
              {writeResult.written_content.professional_summary && (
                <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 8, padding: 14, marginBottom: 14 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#0369a1', margin: '0 0 6px' }}>Professional Summary</h4>
                  <p style={{ margin: 0, fontSize: 13, color: '#0c4a6e', lineHeight: 1.7 }}>{writeResult.written_content.professional_summary}</p>
                </div>
              )}
              {writeResult.written_content.objective_statement && (
                <div style={{ background: '#faf5ff', border: '1px solid #e9d5ff', borderRadius: 8, padding: 14, marginBottom: 14 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#7c3aed', margin: '0 0 6px' }}>Objective Statement</h4>
                  <p style={{ margin: 0, fontSize: 13, color: '#581c87', lineHeight: 1.7 }}>{writeResult.written_content.objective_statement}</p>
                </div>
              )}
              {writeResult.written_content.experience_bullets.length > 0 && (
                <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 8, padding: 14, marginBottom: 14 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#15803d', margin: '0 0 6px' }}>Experience Bullets</h4>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#166534' }}>
                    {writeResult.written_content.experience_bullets.map((b, i) => <li key={i} style={{ marginBottom: 6 }}>{b}</li>)}
                  </ul>
                </div>
              )}
              {writeResult.written_content.skills_section.technical && (
                <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: 14 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#92400e', margin: '0 0 6px' }}>Skills</h4>
                  <div style={{ fontSize: 13, color: '#78350f' }}>
                    <strong>Technical: </strong>{writeResult.written_content.skills_section.technical?.join(', ')}<br />
                    {writeResult.written_content.skills_section.tools && <><strong>Tools: </strong>{writeResult.written_content.skills_section.tools.join(', ')}</>}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Review Tab ───────────────────────────────────────────────────── */}
      {tab === 'review' && (
        <div>
          <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#6b7280', display: 'block', marginBottom: 4 }}>Target Role (optional)</label>
              <input value={targetRole} onChange={e => setTargetRole(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }} />
            </div>
          </div>
          <textarea value={jdText} onChange={e => setJdText(e.target.value)}
            placeholder="Paste job description for contextual review (optional)…"
            rows={3}
            style={{ width: '100%', padding: 10, border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13, fontFamily: 'inherit', resize: 'vertical', marginBottom: 12, boxSizing: 'border-box' }} />
          <button onClick={runReview} disabled={loading}
            style={{ padding: '9px 24px', background: '#059669', color: '#fff', border: 'none', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer', fontWeight: 700, fontSize: 14, opacity: loading ? 0.7 : 1 }}>
            {loading ? 'Reviewing…' : '🔍 Review Resume'}
          </button>

          {reviewResult && (
            <div style={{ marginTop: 20 }}>
              <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                <div style={{
                  background: reviewResult.interview_probability === 'high' ? '#f0fdf4' : reviewResult.interview_probability === 'medium' ? '#fffbeb' : '#fef2f2',
                  borderRadius: 10, padding: '12px 20px', border: '2px solid #e5e7eb',
                }}>
                  <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600 }}>INTERVIEW PROBABILITY</div>
                  <div style={{
                    fontSize: 20, fontWeight: 800,
                    color: reviewResult.interview_probability === 'high' ? '#16a34a' : reviewResult.interview_probability === 'medium' ? '#d97706' : '#ef4444'
                  }}>{reviewResult.interview_probability.toUpperCase()}</div>
                </div>
                <div style={{ flex: 1, background: '#f8fafc', borderRadius: 10, padding: '12px 16px', border: '1px solid #e5e7eb' }}>
                  <p style={{ margin: 0, fontSize: 13, color: '#374151', lineHeight: 1.6 }}>{reviewResult.overall_verdict}</p>
                </div>
              </div>

              <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>Section-by-Section Feedback</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
                {Object.entries(reviewResult.sections).map(([section, fb]) => (
                  <div key={section} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <strong style={{ fontSize: 12, textTransform: 'capitalize' }}>{section.replace(/_/g, ' ')}</strong>
                      <span style={{ fontWeight: 700, fontSize: 13, color: fb.score >= 7 ? '#16a34a' : fb.score >= 5 ? '#d97706' : '#ef4444' }}>{fb.score}/10</span>
                    </div>
                    <ScoreBar score={fb.score} max={10} />
                    <p style={{ margin: '6px 0 4px', fontSize: 12, color: '#4b5563' }}>{fb.feedback}</p>
                    {fb.fixes.map((f, i) => <div key={i} style={{ fontSize: 11, color: '#b91c1c', marginTop: 2 }}>→ {f}</div>)}
                  </div>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 8, padding: 12 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#c2410c', margin: '0 0 8px' }}>Top 3 Immediate Actions</h4>
                  <ol style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: '#7c2d12' }}>
                    {reviewResult.top_3_immediate_actions.map((a, i) => <li key={i} style={{ marginBottom: 6 }}>{a}</li>)}
                  </ol>
                </div>
                <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 8, padding: 12 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#0f766e', margin: '0 0 8px' }}>Interview Tips</h4>
                  <ul style={{ margin: 0, paddingLeft: 16, fontSize: 13, color: '#134e4a' }}>
                    {reviewResult.interview_tips.map((t, i) => <li key={i} style={{ marginBottom: 4 }}>{t}</li>)}
                  </ul>
                </div>
              </div>

              {reviewResult.red_flags.length > 0 && (
                <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: 12, marginTop: 12 }}>
                  <h4 style={{ fontSize: 13, fontWeight: 700, color: '#dc2626', margin: '0 0 6px' }}>🚩 Red Flags</h4>
                  <ul style={{ margin: 0, paddingLeft: 16, fontSize: 13, color: '#b91c1c' }}>
                    {reviewResult.red_flags.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
