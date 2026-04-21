import type { Dispatch, SetStateAction } from 'react'
import type { JobDescriptionResponse, JobSearchResult, JobSource } from './types'

type JobsPageProps = {
  jobExtractUrl: string
  setJobExtractUrl: Dispatch<SetStateAction<string>>
  jdText: string
  setJdText: Dispatch<SetStateAction<string>>
  extractedJob: JobDescriptionResponse | null
  handleExtractJob: () => Promise<void>
  jobKeywords: string
  setJobKeywords: Dispatch<SetStateAction<string>>
  jobLocations: string
  setJobLocations: Dispatch<SetStateAction<string>>
  selectedSources: string[]
  jobSources: JobSource[]
  toggleSource: (sourceId: string) => void
  handleSearchJobs: () => Promise<void>
  jobMatches: JobSearchResult[]
}

export function JobsPage({
  jobExtractUrl,
  setJobExtractUrl,
  jdText,
  setJdText,
  extractedJob,
  handleExtractJob,
  jobKeywords,
  setJobKeywords,
  jobLocations,
  setJobLocations,
  selectedSources,
  jobSources,
  toggleSource,
  handleSearchJobs,
  jobMatches,
}: JobsPageProps) {
  return (
    <div className="row g-4">
      <div className="col-lg-4">
        <div className="card shadow-sm border-0 h-100">
          <div className="card-body p-4">
            <h2 className="h4 mb-3">Job Discovery</h2>
            <p className="text-secondary small mb-4">
              Search trusted portals, extract job descriptions, and map openings to the resume signals already captured by the app.
            </p>

            <div className="mb-3">
              <label className="form-label" htmlFor="job-extract-url">
                Job posting URL
              </label>
              <input
                id="job-extract-url"
                className="form-control"
                value={jobExtractUrl}
                onChange={(event) => setJobExtractUrl(event.target.value)}
                placeholder="https://www.linkedin.com/jobs/view/..."
              />
            </div>

            <div className="mb-3">
              <label className="form-label" htmlFor="job-description-text">
                Job description text
              </label>
              <textarea
                id="job-description-text"
                className="form-control"
                rows={8}
                value={jdText}
                onChange={(event) => setJdText(event.target.value)}
                placeholder="Paste the job description here if you do not have a URL."
              />
            </div>

            <div className="d-grid gap-2">
              <button type="button" className="btn btn-outline-primary" onClick={() => void handleExtractJob()}>
                Extract job details
              </button>
            </div>

            {extractedJob ? (
              <div className="alert alert-info mt-4 mb-0">
                <div className="fw-semibold">{extractedJob.title || 'Untitled role'}</div>
                <div className="small text-secondary">{extractedJob.company || 'Unknown company'}</div>
                <div className="small mt-2">
                  Source: {extractedJob.source} ({extractedJob.source_type})
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="col-lg-8">
        <div className="card shadow-sm border-0 mb-4">
          <div className="card-body p-4">
            <div className="row g-3 align-items-end">
              <div className="col-md-6">
                <label className="form-label" htmlFor="job-keywords">
                  Keywords
                </label>
                <input
                  id="job-keywords"
                  className="form-control"
                  value={jobKeywords}
                  onChange={(event) => setJobKeywords(event.target.value)}
                  placeholder="frontend engineer, react, llm"
                />
              </div>
              <div className="col-md-6">
                <label className="form-label" htmlFor="job-locations">
                  Locations
                </label>
                <input
                  id="job-locations"
                  className="form-control"
                  value={jobLocations}
                  onChange={(event) => setJobLocations(event.target.value)}
                  placeholder="Remote, Bengaluru, London"
                />
              </div>
            </div>

            <div className="mt-4">
              <div className="fw-semibold mb-2">Trusted job sources</div>
              <div className="d-flex flex-wrap gap-2">
                {jobSources.map((source) => {
                  const active = selectedSources.includes(source.id)
                  return (
                    <button
                      key={source.id}
                      type="button"
                      className={`btn btn-sm ${active ? 'btn-primary' : 'btn-outline-secondary'}`}
                      onClick={() => toggleSource(source.id)}
                    >
                      {source.label}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="d-flex justify-content-end mt-4">
              <button type="button" className="btn btn-primary" onClick={() => void handleSearchJobs()}>
                Search jobs
              </button>
            </div>
          </div>
        </div>

        <div className="card shadow-sm border-0">
          <div className="card-body p-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h3 className="h5 mb-0">Matched opportunities</h3>
              <span className="badge text-bg-light">{jobMatches.length} results</span>
            </div>

            {jobMatches.length === 0 ? (
              <div className="text-secondary">
                No job matches yet. Extract a JD or search with keywords and locations to populate this panel.
              </div>
            ) : (
              <div className="d-grid gap-3">
                {jobMatches.map((job) => (
                  <article key={job.id} className="border rounded-4 p-3 bg-body-tertiary">
                    <div className="d-flex justify-content-between gap-3 flex-wrap">
                      <div>
                        <a href={job.url} target="_blank" rel="noreferrer" className="fw-semibold text-decoration-none">
                          {job.title}
                        </a>
                        <div className="small text-secondary">
                          {job.company} • {job.location} • {job.source}
                        </div>
                      </div>
                      {job.ats_score != null ? (
                        <span className="badge text-bg-success align-self-start">ATS {Math.round(job.ats_score)}%</span>
                      ) : null}
                    </div>
                    <p className="small text-secondary mb-0 mt-2">{job.summary}</p>
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
