import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import { useAuth } from './AuthContext'
import type { ParsedFields, UserProfile } from './types'

interface ProfilePageProps {
  onNavigateToResume: () => void
}

export function ProfilePage({ onNavigateToResume }: ProfilePageProps) {
  const { user, jwt, logout } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [uploadSuccess, setUploadSuccess] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!jwt) {
      setLoading(false)
      return
    }
    api.getMyProfile(jwt)
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoading(false))
  }, [jwt])

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadError('')
    setUploadSuccess('')
    try {
      const result = await api.parseResumeAuthenticated(file, jwt)
      setUploadSuccess(`Resume parsed: ${result.parsed_fields?.name ?? file.name}`)
      // Refresh profile
      const updated = await api.getMyProfile(jwt)
      setProfile(updated)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  if (loading) {
    return (
      <div className="d-flex justify-content-center py-5">
        <div className="spinner-border text-primary" role="status" />
      </div>
    )
  }

  const resumeData = profile?.resume_data as ParsedFields | null | undefined

  return (
    <div className="container py-5" style={{ maxWidth: 780 }}>
      {/* User card */}
      <div className="card border-0 rounded-4 shadow-sm mb-4">
        <div className="card-body p-4 d-flex align-items-center gap-4">
          <div
            className="rounded-circle bg-primary d-flex align-items-center justify-content-center text-white fs-3 fw-bold flex-shrink-0"
            style={{ width: 64, height: 64 }}
          >
            {user?.full_name?.[0]?.toUpperCase() ?? user?.email?.[0]?.toUpperCase() ?? '?'}
          </div>
          <div className="flex-grow-1">
            <h2 className="h4 mb-1 fw-bold">{user?.full_name ?? 'User'}</h2>
            <div className="text-secondary small">{user?.email}</div>
            <span className="badge bg-primary-subtle text-primary-emphasis border mt-1">{user?.role}</span>
          </div>
          <button className="btn btn-outline-secondary btn-sm" onClick={logout}>
            Sign Out
          </button>
        </div>
      </div>

      {/* Resume data */}
      <div className="card border-0 rounded-4 shadow-sm mb-4">
        <div className="card-body p-4">
          <div className="d-flex align-items-center justify-content-between mb-3">
            <h3 className="h5 fw-semibold mb-0">Resume Profile</h3>
            <div className="d-flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                className="d-none"
                onChange={handleFileUpload}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? (
                  <><span className="spinner-border spinner-border-sm me-1" />Parsing…</>
                ) : (
                  'Upload Resume'
                )}
              </button>
              {resumeData && (
                <button className="btn btn-outline-secondary btn-sm" onClick={onNavigateToResume}>
                  Analyze
                </button>
              )}
            </div>
          </div>

          {uploadError && <div className="alert alert-danger py-2 small mb-3">{uploadError}</div>}
          {uploadSuccess && <div className="alert alert-success py-2 small mb-3">{uploadSuccess}</div>}

          {resumeData ? (
            <div className="row g-3">
              {resumeData.name && (
                <div className="col-12">
                  <div className="small text-secondary text-uppercase fw-semibold mb-1">Name</div>
                  <div className="fw-semibold">{resumeData.name}</div>
                </div>
              )}
              {resumeData.emails.length > 0 && (
                <div className="col-md-6">
                  <div className="small text-secondary text-uppercase fw-semibold mb-1">Emails</div>
                  {resumeData.emails.map((e) => (
                    <div key={e} className="small">{e}</div>
                  ))}
                </div>
              )}
              {resumeData.phones.length > 0 && (
                <div className="col-md-6">
                  <div className="small text-secondary text-uppercase fw-semibold mb-1">Phone</div>
                  {resumeData.phones.map((p) => (
                    <div key={p} className="small">{p}</div>
                  ))}
                </div>
              )}
              {resumeData.skills.length > 0 && (
                <div className="col-12">
                  <div className="small text-secondary text-uppercase fw-semibold mb-2">Skills</div>
                  <div className="d-flex flex-wrap gap-2">
                    {resumeData.skills.map((s) => (
                      <span key={s} className="badge bg-primary-subtle text-primary-emphasis border">{s}</span>
                    ))}
                  </div>
                </div>
              )}
              {resumeData.companies.length > 0 && (
                <div className="col-12">
                  <div className="small text-secondary text-uppercase fw-semibold mb-2">Companies</div>
                  <div className="d-flex flex-wrap gap-2">
                    {resumeData.companies.map((c) => (
                      <span key={c} className="badge bg-secondary-subtle text-secondary-emphasis border">{c}</span>
                    ))}
                  </div>
                </div>
              )}
              {resumeData.education.length > 0 && (
                <div className="col-12">
                  <div className="small text-secondary text-uppercase fw-semibold mb-1">Education</div>
                  <div className="small">{resumeData.education.join(', ')}</div>
                </div>
              )}
              {resumeData.summary && (
                <div className="col-12">
                  <div className="small text-secondary text-uppercase fw-semibold mb-1">Summary</div>
                  <div className="small text-secondary border rounded-3 p-3 bg-body-tertiary">{resumeData.summary}</div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-4 text-secondary">
              <div className="fs-1 mb-2">📄</div>
              <div className="fw-semibold mb-1">No resume uploaded yet</div>
              <div className="small">Upload a PDF, DOCX, or TXT file to auto-populate your profile.</div>
            </div>
          )}
        </div>
      </div>

      {profile?.updated_at && (
        <div className="text-end small text-secondary">
          Last updated {new Date(profile.updated_at).toLocaleString()}
        </div>
      )}
    </div>
  )
}
