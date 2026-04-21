import type { Dispatch, SetStateAction } from 'react'
import type { ResumeTemplate } from './types'

type TemplatesPageProps = {
  templates: ResumeTemplate[]
  templateName: string
  setTemplateName: Dispatch<SetStateAction<string>>
  templateRole: string
  setTemplateRole: Dispatch<SetStateAction<string>>
  templateStyle: string
  setTemplateStyle: Dispatch<SetStateAction<string>>
  templateNotes: string
  setTemplateNotes: Dispatch<SetStateAction<string>>
  handleDesignTemplate: () => Promise<void>
  generatedTemplate: ResumeTemplate | null
  loading: boolean
}

export function TemplatesPage({
  templates,
  templateName,
  setTemplateName,
  templateRole,
  setTemplateRole,
  templateStyle,
  setTemplateStyle,
  templateNotes,
  setTemplateNotes,
  handleDesignTemplate,
  generatedTemplate,
  loading,
}: TemplatesPageProps) {
  const previewTemplate = generatedTemplate ?? templates[0] ?? null

  return (
    <div className="row g-4">
      <div className="col-lg-4">
        <div className="card shadow-sm border-0 h-100">
          <div className="card-body p-4">
            <h2 className="h4 mb-3">Template Studio</h2>
            <p className="text-secondary small">
              Generate new resume layouts with Figma-oriented prompts and reuse previously stored design templates.
            </p>

            <div className="mb-3">
              <label className="form-label" htmlFor="template-name">
                Template name
              </label>
              <input
                id="template-name"
                className="form-control"
                value={templateName}
                onChange={(event) => setTemplateName(event.target.value)}
              />
            </div>

            <div className="mb-3">
              <label className="form-label" htmlFor="template-role">
                Target role
              </label>
              <input
                id="template-role"
                className="form-control"
                value={templateRole}
                onChange={(event) => setTemplateRole(event.target.value)}
              />
            </div>

            <div className="mb-3">
              <label className="form-label" htmlFor="template-style">
                Style direction
              </label>
              <input
                id="template-style"
                className="form-control"
                value={templateStyle}
                onChange={(event) => setTemplateStyle(event.target.value)}
                placeholder="bold editorial, executive minimal, modern product"
              />
            </div>

            <div className="mb-3">
              <label className="form-label" htmlFor="template-notes">
                Design notes
              </label>
              <textarea
                id="template-notes"
                className="form-control"
                rows={6}
                value={templateNotes}
                onChange={(event) => setTemplateNotes(event.target.value)}
              />
            </div>

            <div className="d-grid">
              <button type="button" className="btn btn-primary" onClick={() => void handleDesignTemplate()} disabled={loading}>
                {loading ? 'Designing…' : 'Design template'}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="col-lg-8">
        <div className="card shadow-sm border-0 mb-4">
          <div className="card-body p-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <h3 className="h5 mb-0">Available templates</h3>
              <span className="badge text-bg-light">{templates.length} saved</span>
            </div>
            {templates.length === 0 ? (
              <div className="text-secondary">
                No saved templates yet. Create one from the form to seed the library.
              </div>
            ) : (
              <div className="row g-3">
                {templates.map((template) => (
                  <div key={template.id} className="col-md-6">
                    <div className="border rounded-4 p-3 h-100 bg-body-tertiary">
                      <div className="fw-semibold">{template.name}</div>
                      <div className="small text-secondary">{template.target_role}</div>
                      <div className="d-flex gap-2 mt-2 flex-wrap">
                        <span className="badge text-bg-light">{template.style}</span>
                        <span className="badge text-bg-light">{template.source}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="card shadow-sm border-0">
          <div className="card-body p-4">
            <h3 className="h5 mb-3">Preview</h3>
            {!previewTemplate ? (
              <div className="text-secondary">Generate or load a template to inspect its design tokens and Figma prompt.</div>
            ) : (
              <>
                <div className="mb-3">
                  <div className="fw-semibold">{previewTemplate.name}</div>
                  <div className="small text-secondary">
                    {previewTemplate.target_role} • {previewTemplate.style}
                  </div>
                </div>

                <div className="mb-3">
                  <div className="small text-uppercase text-secondary fw-semibold mb-2">Sections</div>
                  <div className="d-flex flex-wrap gap-2">
                    {previewTemplate.sections.map((section) => (
                      <span key={section} className="badge text-bg-light">
                        {section}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mb-3">
                  <div className="small text-uppercase text-secondary fw-semibold mb-2">Figma prompt</div>
                  <pre className="bg-body-tertiary rounded-4 p-3 small mb-0">{previewTemplate.figma_prompt}</pre>
                </div>

                <div className="mb-3">
                  <div className="small text-uppercase text-secondary fw-semibold mb-2">Design tokens</div>
                  <div className="row g-2">
                    {Object.entries(previewTemplate.design_tokens).map(([key, value]) => (
                      <div key={key} className="col-md-6">
                        <div className="border rounded-3 px-3 py-2 h-100">
                          <div className="small text-secondary">{key}</div>
                          <div className="fw-semibold">{value}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="small text-uppercase text-secondary fw-semibold mb-2">Preview markdown</div>
                  <pre className="bg-body-tertiary rounded-4 p-3 small mb-0">{previewTemplate.preview_markdown}</pre>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
