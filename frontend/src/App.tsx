import type { ChangeEvent, FormEvent } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import { api, getStoredApiKey, setStoredApiKey } from './api'
import { ChatPage } from './ChatPage'
import { JobHuntPage } from './JobHuntPage'
import { JobsPage } from './JobsPage'
import { TemplatesPage } from './TemplatesPage'
import type {
  AgentSummary,
  ApiKeyCreateResponse,
  AuthStatusResponse,
  CareerAnalytics,
  DiagnosticRunResponse,
  ExecutionResponse,
  HealthResponse,
  JobDescriptionResponse,
  JobSearchResult,
  JobSource,
  ModelSummary,
  ResumeAnalysis,
  ResumeChatResponse,
  ResumeTemplate,
  SelfHealingStatus,
} from './types'

type PageKey = 'overview' | 'resume' | 'jobs' | 'templates' | 'chat' | 'hunt'

const INITIAL_CONTEXT = '{\n  "priority": "normal",\n  "channel": "web"\n}'

function App() {
  const [page, setPage] = useState<PageKey>('overview')
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [models, setModels] = useState<ModelSummary[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [history, setHistory] = useState<ExecutionResponse[]>([])
  const [authStatus, setAuthStatus] = useState<AuthStatusResponse | null>(null)
  const [selfHealing, setSelfHealing] = useState<SelfHealingStatus | null>(null)
  const [analytics, setAnalytics] = useState<CareerAnalytics | null>(null)
  const [jobSources, setJobSources] = useState<JobSource[]>([])
  const [templates, setTemplates] = useState<ResumeTemplate[]>([])
  const [apiKey, setApiKey] = useState(() => getStoredApiKey())
  const [bootstrapToken, setBootstrapToken] = useState('')
  const [bootstrapName, setBootstrapName] = useState('local-admin')
  const [bootstrapResult, setBootstrapResult] = useState<ApiKeyCreateResponse | null>(null)
  const [bootError, setBootError] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [loading, setLoading] = useState(false)
  const [diagnostics, setDiagnostics] = useState<DiagnosticRunResponse | null>(null)
  const [diagLoading, setDiagLoading] = useState(false)
  const [diagError, setDiagError] = useState('')

  const [task, setTask] = useState('')
  const [agentName, setAgentName] = useState('')
  const [modelProfile, setModelProfile] = useState('')
  const [contextText, setContextText] = useState(INITIAL_CONTEXT)
  const [activeExecution, setActiveExecution] = useState<ExecutionResponse | null>(null)

  const [resumeFilename, setResumeFilename] = useState('')
  const [resumeText, setResumeText] = useState('')
  const [jdText, setJdText] = useState('')
  const [resumeAnalysis, setResumeAnalysis] = useState<ResumeAnalysis | null>(null)
  const [resumeQuestion, setResumeQuestion] = useState('')
  const [resumeChat, setResumeChat] = useState<ResumeChatResponse | null>(null)

  const [jobExtractUrl, setJobExtractUrl] = useState('')
  const [extractedJob, setExtractedJob] = useState<JobDescriptionResponse | null>(null)
  const [jobKeywords, setJobKeywords] = useState('')
  const [jobLocations, setJobLocations] = useState('Remote')
  const [selectedSources, setSelectedSources] = useState<string[]>([])
  const [jobMatches, setJobMatches] = useState<JobSearchResult[]>([])

  const [templateName, setTemplateName] = useState('Product Engineer Sprint')
  const [templateRole, setTemplateRole] = useState('Senior Frontend GenAI Engineer')
  const [templateStyle, setTemplateStyle] = useState('bold editorial')
  const [templateNotes, setTemplateNotes] = useState('Design for a modern one-page resume with a strong summary, metrics, and ATS readability.')
  const [generatedTemplate, setGeneratedTemplate] = useState<ResumeTemplate | null>(null)

  const localModels = useMemo(
    () => models.filter((model) => model.provider === 'llama-cpp' || model.provider.startsWith('ollama')),
    [models],
  )

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.name === agentName) ?? null,
    [agents, agentName],
  )

  const loadProtectedData = useCallback(async () => {
    const [
      agentResult,
      modelResult,
      historyResult,
      selfHealingResult,
      analyticsResult,
      diagResult,
      templateResult,
      sourceResult,
    ] = await Promise.all([
      api.getAgents(),
      api.getModels(),
      api.getExecutions(),
      api.getSelfHealingStatus().catch(() => null),
      api.getAnalytics().catch(() => null),
      api.getLatestDiagnosticReport().catch(() => null),
      api.getResumeTemplates().catch(() => ({ templates: [] })),
      api.getJobSources().catch(() => ({ sources: [] })),
    ])
    setAgents(agentResult)
    setModels(modelResult.models)
    setHistory(historyResult.executions)
    setSelfHealing(selfHealingResult)
    setAnalytics(analyticsResult)
    setDiagnostics(diagResult)
    setTemplates(templateResult.templates)
    setJobSources(sourceResult.sources)
    if (!selectedSources.length && sourceResult.sources.length) {
      setSelectedSources(sourceResult.sources.slice(0, 3).map((source) => source.id))
    }
  }, [selectedSources.length])

  useEffect(() => {
    let ignore = false

    async function bootstrap() {
      try {
        const healthResult = await api.getHealth()
        if (ignore) return
        setHealth(healthResult)

        const authResult = await api.getAuthStatus()
        if (ignore) return
        setAuthStatus(authResult)

        if (!authResult.auth_enabled || apiKey) {
          await loadProtectedData()
        }
      } catch (error) {
        if (!ignore) {
          setBootError(error instanceof Error ? error.message : 'Unable to connect to the backend.')
        }
      }
    }

    bootstrap()
    return () => {
      ignore = true
    }
  }, [apiKey, loadProtectedData])

  useEffect(() => {
    setStoredApiKey(apiKey)
  }, [apiKey])

  async function handleBootstrap(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBootError('')
    try {
      const created = await api.bootstrapAdminKey(bootstrapToken, bootstrapName)
      setBootstrapResult(created)
      setStoredApiKey(created.key)
      setApiKey(created.key)
      setAuthStatus(await api.getAuthStatus())
      await loadProtectedData()
    } catch (error) {
      setBootError(error instanceof Error ? error.message : 'Bootstrap failed.')
    }
  }

  async function handleLoadApiKey() {
    setBootError('')
    try {
      setStoredApiKey(apiKey)
      setAuthStatus(await api.getAuthStatus())
      await loadProtectedData()
    } catch (error) {
      setBootError(error instanceof Error ? error.message : 'Failed to load data with the API key.')
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitError('')
    setLoading(true)
    try {
      const parsedContext = contextText.trim() ? (JSON.parse(contextText) as Record<string, unknown>) : {}
      const execution = await api.executeTask({
        task,
        agent_name: agentName || undefined,
        model_profile: modelProfile || undefined,
        context: parsedContext,
      })
      setActiveExecution(execution)
      setHistory((current) => [execution, ...current].slice(0, 10))
      setPage('overview')
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Task execution failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleRunDiagnostics() {
    setDiagLoading(true)
    setDiagError('')
    try {
      const result = await api.runDiagnostics()
      setDiagnostics(result)
    } catch (error) {
      setDiagError(error instanceof Error ? error.message : 'Diagnostics failed.')
    } finally {
      setDiagLoading(false)
    }
  }

  async function handleResumeUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setLoading(true)
    setSubmitError('')
    try {
      const parsed = await api.parseResume(file)
      setResumeFilename(parsed.filename)
      setResumeText(parsed.text)
      const analysis = await api.analyzeResume(parsed.text, jdText, parsed.filename, preferredResumeModel(localModels))
      setResumeAnalysis(analysis)
      if (analysis.ats_keywords.length) {
        const results = await api.searchJobs({
          keywords: analysis.ats_keywords.slice(0, 6),
          locations: parseCsv(jobLocations),
          sources: selectedSources,
        })
        setJobMatches(results)
      }
      const analyticsResult = await api.getAnalytics().catch(() => null)
      if (analyticsResult) setAnalytics(analyticsResult)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Resume processing failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleResumeAnalysis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!resumeText.trim()) {
      setSubmitError('Upload or paste a resume before analysis.')
      return
    }
    setLoading(true)
    setSubmitError('')
    try {
      const analysis = await api.analyzeResume(resumeText, jdText, resumeFilename || undefined, preferredResumeModel(localModels))
      setResumeAnalysis(analysis)
      const analyticsResult = await api.getAnalytics().catch(() => null)
      if (analyticsResult) setAnalytics(analyticsResult)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Resume analysis failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleResumeQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!resumeText.trim() || !resumeQuestion.trim()) {
      return
    }
    setLoading(true)
    setSubmitError('')
    try {
      const response = await api.askResume(
        resumeQuestion,
        resumeText,
        jdText,
        preferredResumeModel(localModels),
      )
      setResumeChat(response)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Resume chat failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleExtractJob() {
    setLoading(true)
    setSubmitError('')
    try {
      const extracted = await api.extractJobDescription({
        url: jobExtractUrl.trim() || undefined,
        text: jdText.trim() || undefined,
      })
      setExtractedJob(extracted)
      setJdText(extracted.description)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Job description extraction failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSearchJobs() {
    if (!parseCsv(jobKeywords).length) {
      setSubmitError('Add at least one job keyword before searching.')
      return
    }
    setLoading(true)
    setSubmitError('')
    try {
      const results = await api.searchJobs({
        keywords: parseCsv(jobKeywords),
        locations: parseCsv(jobLocations),
        sources: selectedSources,
      })
      setJobMatches(results)
      const analyticsResult = await api.getAnalytics().catch(() => null)
      if (analyticsResult) setAnalytics(analyticsResult)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Job search failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleDesignTemplate() {
    setLoading(true)
    setSubmitError('')
    try {
      const created = await api.designResumeTemplate({
        name: templateName,
        target_role: templateRole,
        style: templateStyle,
        notes: templateNotes,
        model_profile: preferredTemplateModel(localModels),
      })
      setGeneratedTemplate(created)
      const refreshed = await api.getResumeTemplates()
      setTemplates(refreshed.templates)
      const analyticsResult = await api.getAnalytics().catch(() => null)
      if (analyticsResult) setAnalytics(analyticsResult)
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Template design failed.')
    } finally {
      setLoading(false)
    }
  }

  function toggleSource(sourceId: string) {
    setSelectedSources((current) =>
      current.includes(sourceId)
        ? current.filter((item) => item !== sourceId)
        : [...current, sourceId],
    )
  }

  return (
    <div className="app-page">
      <nav className="navbar navbar-expand-lg border-bottom bg-white bg-opacity-75 sticky-top">
        <div className="container py-2">
          <span className="navbar-brand fw-semibold mb-0 h1">Antypity</span>
          <span className="badge rounded-pill text-bg-primary">Career OS</span>
        </div>
      </nav>

      <div className="container py-5">
        <section className="hero-gradient rounded-5 text-white p-4 p-lg-5 shadow-lg mb-4">
          <div className="row g-4 align-items-center">
            <div className="col-lg-7">
              <div className="text-uppercase small fw-semibold opacity-75 mb-2">Local models, trusted sources, production baseline</div>
              <h1 className="display-5 fw-bold mb-3">Resume intelligence, job discovery, and orchestration in one surface.</h1>
              <p className="lead mb-0 opacity-90">
                The platform now combines multi-agent execution, local LLaMA/Ollama processing, resume and JD analysis,
                resume chat, trusted-portal job discovery, and Figma-oriented resume template design.
              </p>
            </div>
            <div className="col-lg-5">
              <div className="row g-3">
                <StatusTile label="API endpoint" value={api.baseUrl} />
                <StatusTile label="Health" value={health?.status ?? 'unknown'} />
                <StatusTile label="Local models" value={localModels.length ? `${localModels.length} available` : 'not configured'} />
                <StatusTile label="Templates" value={templates.length ? `${templates.length} loaded` : 'none'} />
              </div>
            </div>
          </div>
        </section>

        {bootError ? (
          <div className="alert alert-danger shadow-sm" role="alert">
            <strong>Connection error.</strong> {bootError}
          </div>
        ) : null}

        {submitError ? (
          <div className="alert alert-danger shadow-sm" role="alert">
            <strong>Request failed.</strong> {submitError}
          </div>
        ) : null}

        <div className="row g-4 mb-4">
          <div className="col-xl-4">
            <div className="card glass-card border-0 rounded-4 h-100">
              <div className="card-body p-4">
                <div className="d-flex justify-content-between align-items-start mb-3">
                  <div>
                    <div className="text-uppercase small text-secondary fw-semibold">Access</div>
                    <h2 className="section-title h4 mb-0">Authentication</h2>
                  </div>
                  <span className="badge soft-badge rounded-pill">
                    {health?.auth_enabled ? 'Protected' : 'Open'}
                  </span>
                </div>

                <div className="mb-3">
                  <label className="form-label" htmlFor="api-key-input">API key</label>
                  <input
                    id="api-key-input"
                    name="apiKey"
                    className="form-control form-control-lg"
                    type="password"
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder="Paste an admin, operator, or viewer key"
                  />
                </div>
                <button type="button" className="btn btn-primary w-100 mb-3" onClick={handleLoadApiKey}>
                  Load protected data
                </button>

                {health?.auth_enabled && authStatus?.bootstrap_required ? (
                  <form onSubmit={handleBootstrap} className="border-top pt-3">
                    <div className="mb-3">
                      <label className="form-label" htmlFor="bootstrap-token-input">Bootstrap token</label>
                      <input
                        id="bootstrap-token-input"
                        name="bootstrapToken"
                        className="form-control"
                        type="password"
                        value={bootstrapToken}
                        onChange={(event) => setBootstrapToken(event.target.value)}
                        placeholder="BOOTSTRAP_ADMIN_TOKEN or SECRET_KEY"
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label className="form-label" htmlFor="bootstrap-name-input">First admin key name</label>
                      <input
                        id="bootstrap-name-input"
                        name="bootstrapName"
                        className="form-control"
                        type="text"
                        value={bootstrapName}
                        onChange={(event) => setBootstrapName(event.target.value)}
                        placeholder="e.g. ops-admin"
                        required
                      />
                    </div>
                    <button type="submit" className="btn btn-outline-primary w-100">
                      Create first admin key
                    </button>
                  </form>
                ) : null}

                {bootstrapResult ? (
                  <div className="alert alert-success mt-3 mb-0" role="alert">
                    Admin key created for <strong>{bootstrapResult.name}</strong>.
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="col-xl-8">
            <div className="card glass-card border-0 rounded-4 h-100">
              <div className="card-body p-4">
                <div className="text-uppercase small text-secondary fw-semibold mb-2">Navigation</div>
                <div className="d-flex flex-wrap gap-2">
                  {[
                    ['overview', 'Overview'],
                    ['resume', 'Resume Lab'],
                    ['hunt', '🎯 AI Job Hunt'],
                    ['chat', 'Career Chat'],
                    ['jobs', 'Job Discovery'],
                    ['templates', 'Template Studio'],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      className={`btn ${page === value ? 'btn-primary' : 'btn-outline-primary'}`}
                      onClick={() => setPage(value as PageKey)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div className="row g-3 mt-3">
                  <MetricCard label="Resume analyses" value={String(analytics?.total_resume_analyses ?? 0)} />
                  <MetricCard label="Job queries" value={String(analytics?.total_job_queries ?? 0)} />
                  <MetricCard label="Job results" value={String(analytics?.total_job_results ?? 0)} />
                  <MetricCard label="Avg match score" value={`${analytics?.average_match_score ?? 0}%`} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {page === 'overview' ? (
          <OverviewPage
            agents={agents}
            models={models}
            selectedAgent={selectedAgent}
            task={task}
            setTask={setTask}
            agentName={agentName}
            setAgentName={setAgentName}
            modelProfile={modelProfile}
            setModelProfile={setModelProfile}
            contextText={contextText}
            setContextText={setContextText}
            loading={loading}
            handleSubmit={handleSubmit}
            activeExecution={activeExecution}
            history={history}
            selfHealing={selfHealing}
            diagnostics={diagnostics}
            diagLoading={diagLoading}
            diagError={diagError}
            handleRunDiagnostics={handleRunDiagnostics}
          />
        ) : null}

        {page === 'resume' ? (
          <ResumePage
            resumeFilename={resumeFilename}
            resumeText={resumeText}
            setResumeText={setResumeText}
            jdText={jdText}
            setJdText={setJdText}
            loading={loading}
            handleResumeUpload={handleResumeUpload}
            handleResumeAnalysis={handleResumeAnalysis}
            resumeAnalysis={resumeAnalysis}
            resumeQuestion={resumeQuestion}
            setResumeQuestion={setResumeQuestion}
            handleResumeQuestion={handleResumeQuestion}
            resumeChat={resumeChat}
            localModels={localModels}
          />
        ) : null}

        {page === 'chat' ? <ChatPage /> : null}

        {page === 'hunt' ? <JobHuntPage resumeText={resumeText} /> : null}

        {page === 'jobs' ? (
          <JobsPage
            jobExtractUrl={jobExtractUrl}
            setJobExtractUrl={setJobExtractUrl}
            jdText={jdText}
            setJdText={setJdText}
            extractedJob={extractedJob}
            handleExtractJob={handleExtractJob}
            jobKeywords={jobKeywords}
            setJobKeywords={setJobKeywords}
            jobLocations={jobLocations}
            setJobLocations={setJobLocations}
            selectedSources={selectedSources}
            jobSources={jobSources}
            toggleSource={toggleSource}
            handleSearchJobs={handleSearchJobs}
            jobMatches={jobMatches}
          />
        ) : null}

        {page === 'templates' ? (
          <TemplatesPage
            templates={templates}
            templateName={templateName}
            setTemplateName={setTemplateName}
            templateRole={templateRole}
            setTemplateRole={setTemplateRole}
            templateStyle={templateStyle}
            setTemplateStyle={setTemplateStyle}
            templateNotes={templateNotes}
            setTemplateNotes={setTemplateNotes}
            handleDesignTemplate={handleDesignTemplate}
            generatedTemplate={generatedTemplate}
            loading={loading}
          />
        ) : null}
      </div>
    </div>
  )
}

function OverviewPage(props: {
  agents: AgentSummary[]
  models: ModelSummary[]
  selectedAgent: AgentSummary | null
  task: string
  setTask: (value: string) => void
  agentName: string
  setAgentName: (value: string) => void
  modelProfile: string
  setModelProfile: (value: string) => void
  contextText: string
  setContextText: (value: string) => void
  loading: boolean
  handleSubmit: (event: FormEvent<HTMLFormElement>) => Promise<void>
  activeExecution: ExecutionResponse | null
  history: ExecutionResponse[]
  selfHealing: SelfHealingStatus | null
  diagnostics: DiagnosticRunResponse | null
  diagLoading: boolean
  diagError: string
  handleRunDiagnostics: () => Promise<void>
}) {
  return (
    <div className="row g-4">
      <div className="col-xl-7">
        <div className="card glass-card border-0 rounded-4 h-100">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold">Execution</div>
            <h2 className="section-title h4 mb-3">Multi-agent orchestration console</h2>
            <form onSubmit={props.handleSubmit}>
              <div className="mb-3">
                <label htmlFor="task-input" className="form-label">Task</label>
                <textarea
                  id="task-input"
                  className="form-control"
                  rows={4}
                  value={props.task}
                  onChange={(event) => props.setTask(event.target.value)}
                  placeholder="Describe the task, issue, or workflow objective"
                  required
                />
              </div>

              <div className="row g-3">
                <div className="col-md-6">
                  <label htmlFor="agent-select" className="form-label">Agent</label>
                  <select
                    id="agent-select"
                    className="form-select"
                    value={props.agentName}
                    onChange={(event) => props.setAgentName(event.target.value)}
                  >
                    <option value="">Auto-route across agents</option>
                    {props.agents.map((agent) => (
                      <option key={agent.name} value={agent.name}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="col-md-6">
                  <label htmlFor="model-select" className="form-label">Model profile</label>
                  <select
                    id="model-select"
                    className="form-select"
                    value={props.modelProfile}
                    onChange={(event) => props.setModelProfile(event.target.value)}
                  >
                    <option value="">Use agent default model</option>
                    {props.models.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.id} · {model.provider}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-3">
                <label htmlFor="context-input" className="form-label">Context JSON</label>
                <textarea
                  id="context-input"
                  className="form-control code-block"
                  rows={6}
                  value={props.contextText}
                  onChange={(event) => props.setContextText(event.target.value)}
                />
              </div>

              {props.selectedAgent ? (
                <div className="alert alert-light border mt-3 mb-0">
                  <div className="fw-semibold mb-1">{props.selectedAgent.name}</div>
                  <div className="text-secondary small mb-2">{props.selectedAgent.description}</div>
                  <div className="d-flex flex-wrap gap-2">
                    {props.selectedAgent.capabilities.map((capability) => (
                      <span key={capability} className="badge text-bg-light border">
                        {capability}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="d-flex flex-wrap gap-2 mt-4">
                <button type="submit" className="btn btn-primary btn-lg" disabled={props.loading}>
                  {props.loading ? 'Running orchestration...' : 'Execute task'}
                </button>
                <span className="badge metric-pill rounded-pill px-3 py-2 align-self-center text-secondary">
                  {props.models.length} model profiles available
                </span>
              </div>
            </form>
          </div>
        </div>
      </div>

      <div className="col-xl-5">
        <div className="card glass-card border-0 rounded-4 h-100">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold">Latest result</div>
            <h2 className="section-title h4 mb-3">Execution output</h2>
            {props.activeExecution ? (
              <>
                <div className="d-flex flex-wrap gap-2 mb-3">
                  <span className="badge text-bg-primary">{props.activeExecution.agent_name}</span>
                  <span className="badge text-bg-light border">{props.activeExecution.model_profile ?? 'agent default'}</span>
                  <span className="badge text-bg-light border">{props.activeExecution.provider ?? 'unknown provider'}</span>
                </div>
                <pre className="code-block bg-body-tertiary rounded-4 p-3 mb-0">
                  {props.activeExecution.output}
                </pre>
              </>
            ) : (
              <div className="text-secondary">Run a task to inspect agent routing and output.</div>
            )}
          </div>
        </div>
      </div>

      <div className="col-12">
        <div className="card glass-card border-0 rounded-4">
          <div className="card-body p-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
              <div>
                <div className="text-uppercase small text-secondary fw-semibold">Diagnostics</div>
                <h2 className="section-title h4 mb-0">Platform monitoring</h2>
              </div>
              <button className="btn btn-sm btn-outline-primary" onClick={props.handleRunDiagnostics} disabled={props.diagLoading}>
                {props.diagLoading ? 'Running…' : 'Run Diagnostics'}
              </button>
            </div>
            {props.diagError ? <div className="alert alert-danger py-2">{props.diagError}</div> : null}
            {props.diagnostics ? (
              <div className="d-flex flex-wrap gap-3 align-items-center mb-3">
                <span className={`badge fs-6 px-3 py-2 ${props.diagnostics.status === 'healthy' ? 'bg-success' : props.diagnostics.status === 'degraded' ? 'bg-warning text-dark' : 'bg-danger'}`}>
                  {props.diagnostics.status.toUpperCase()}
                </span>
                <span className="text-secondary small">{new Date(props.diagnostics.created_at).toLocaleString()}</span>
                {props.selfHealing?.last_cycle ? (
                  <span className="text-secondary small">
                    Self-healing: {props.selfHealing.last_cycle.status} at {new Date(props.selfHealing.last_cycle.timestamp).toLocaleTimeString()}
                  </span>
                ) : null}
              </div>
            ) : (
              <div className="text-secondary mb-3">No diagnostic report yet.</div>
            )}
            <div className="table-wrap">
              <table className="table align-middle mb-0">
                <thead>
                  <tr>
                    <th>Created</th>
                    <th>Agent</th>
                    <th>Model</th>
                    <th>Provider</th>
                    <th>Status</th>
                    <th>Output</th>
                  </tr>
                </thead>
                <tbody>
                  {props.history.map((execution) => (
                    <tr key={execution.execution_id}>
                      <td>{new Date(execution.created_at).toLocaleString()}</td>
                      <td>{execution.agent_name}</td>
                      <td>{execution.model_profile ?? 'default'}</td>
                      <td>{execution.provider ?? 'n/a'}</td>
                      <td><span className="badge text-bg-success">{execution.status}</span></td>
                      <td className="text-secondary">{execution.output.slice(0, 120)}{execution.output.length > 120 ? '…' : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ResumePage(props: {
  resumeFilename: string
  resumeText: string
  setResumeText: (value: string) => void
  jdText: string
  setJdText: (value: string) => void
  loading: boolean
  handleResumeUpload: (event: ChangeEvent<HTMLInputElement>) => Promise<void>
  handleResumeAnalysis: (event: FormEvent<HTMLFormElement>) => Promise<void>
  resumeAnalysis: ResumeAnalysis | null
  resumeQuestion: string
  setResumeQuestion: (value: string) => void
  handleResumeQuestion: (event: FormEvent<HTMLFormElement>) => Promise<void>
  resumeChat: ResumeChatResponse | null
  localModels: ModelSummary[]
}) {
  return (
    <div className="row g-4">
      <div className="col-xl-6">
        <div className="card glass-card border-0 rounded-4 h-100">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold">Resume Lab</div>
            <h2 className="section-title h4 mb-3">Local resume and JD analysis</h2>
            <div className="mb-3">
              <label htmlFor="resume-file-input" className="form-label">Upload resume</label>
              <input
                id="resume-file-input"
                type="file"
                className="form-control"
                onChange={props.handleResumeUpload}
                accept=".pdf,.docx,.txt"
              />
              {props.resumeFilename ? <div className="small text-secondary mt-2">Loaded: {props.resumeFilename}</div> : null}
            </div>
            <form onSubmit={props.handleResumeAnalysis}>
              <div className="mb-3">
                <label htmlFor="resume-text-input" className="form-label">Resume text</label>
                <textarea
                  id="resume-text-input"
                  className="form-control"
                  rows={8}
                  value={props.resumeText}
                  onChange={(event) => props.setResumeText(event.target.value)}
                  placeholder="Paste resume text or upload a file"
                />
              </div>
              <div className="mb-3">
                <label htmlFor="resume-jd-input" className="form-label">Job description context</label>
                <textarea
                  id="resume-jd-input"
                  className="form-control"
                  rows={6}
                  value={props.jdText}
                  onChange={(event) => props.setJdText(event.target.value)}
                  placeholder="Paste the target job description to compute fit and missing keywords"
                />
              </div>
              <div className="d-flex flex-wrap gap-2 align-items-center">
                <button type="submit" className="btn btn-primary" disabled={props.loading}>
                  {props.loading ? 'Analyzing…' : 'Analyze resume'}
                </button>
                <span className="small text-secondary">
                  Local models: {props.localModels.map((model) => model.id).join(', ') || 'not configured'}
                </span>
              </div>
            </form>
          </div>
        </div>
      </div>

      <div className="col-xl-6">
        <div className="card glass-card border-0 rounded-4 h-100">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold">Result</div>
            <h2 className="section-title h4 mb-3">ATS insights</h2>
            {props.resumeAnalysis ? (
              <>
                <div className="d-flex flex-wrap gap-2 mb-3">
                  <span className="badge text-bg-primary">Match {props.resumeAnalysis.match_score}%</span>
                  <span className="badge text-bg-light border">{props.resumeAnalysis.model_profile ?? 'default model'}</span>
                  <span className="badge text-bg-light border">{props.resumeAnalysis.provider ?? 'unknown provider'}</span>
                </div>
                <p className="text-secondary">{props.resumeAnalysis.summary}</p>
                <div className="mb-3">
                  <div className="fw-semibold mb-2">ATS keywords</div>
                  <div className="d-flex flex-wrap gap-2">
                    {props.resumeAnalysis.ats_keywords.map((keyword) => (
                      <span key={keyword} className="badge bg-primary-subtle text-primary-emphasis border">
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="row g-3">
                  <InsightList title="Strengths" items={props.resumeAnalysis.strengths} />
                  <InsightList title="Gaps" items={props.resumeAnalysis.gaps} />
                  <InsightList title="Suggestions" items={props.resumeAnalysis.suggestions} />
                  <InsightList title="Recommended roles" items={props.resumeAnalysis.recommended_roles} />
                </div>
              </>
            ) : (
              <div className="text-secondary">Analyze a resume to generate ATS scoring, keywords, strengths, and role recommendations.</div>
            )}
          </div>
        </div>
      </div>

      <div className="col-12">
        <div className="card glass-card border-0 rounded-4">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold">Resume Chatbot</div>
            <h2 className="section-title h4 mb-3">Ask questions about the resume and JD</h2>
            <form onSubmit={props.handleResumeQuestion}>
              <div className="row g-3 align-items-end">
                <div className="col-lg-9">
                  <label htmlFor="resume-question-input" className="form-label">Question</label>
                  <input
                    id="resume-question-input"
                    className="form-control"
                    type="text"
                    value={props.resumeQuestion}
                    onChange={(event) => props.setResumeQuestion(event.target.value)}
                    placeholder="Which bullets should I rewrite for this job?"
                  />
                </div>
                <div className="col-lg-3">
                  <button type="submit" className="btn btn-outline-primary w-100" disabled={props.loading}>
                    Ask
                  </button>
                </div>
              </div>
            </form>
            {props.resumeChat ? (
              <div className="mt-4">
                <div className="d-flex flex-wrap gap-2 mb-2">
                  <span className="badge text-bg-light border">{props.resumeChat.model_profile}</span>
                  <span className="badge text-bg-light border">{props.resumeChat.provider}</span>
                </div>
                <div className="border rounded-4 p-3 bg-body-tertiary">{props.resumeChat.answer}</div>
                <div className="mt-3">
                  <div className="small text-secondary text-uppercase fw-semibold mb-2">Suggested follow-ups</div>
                  <div className="d-flex flex-wrap gap-2">
                    {props.resumeChat.suggested_questions.map((question) => (
                      <span key={question} className="badge text-bg-light border">{question}</span>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatusTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="col-sm-6">
      <div className="status-tile rounded-4 bg-white bg-opacity-25 p-3 h-100">
        <div className="status-label mb-2">{label}</div>
        <div className="fw-semibold fs-5 text-break">{value}</div>
      </div>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="col-md-3">
      <div className="border rounded-4 p-3 bg-white shadow-sm h-100">
        <div className="small text-secondary text-uppercase fw-semibold mb-1">{label}</div>
        <div className="h4 mb-0">{value}</div>
      </div>
    </div>
  )
}

function InsightList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="col-md-6">
      <div className="border rounded-4 p-3 h-100 bg-white">
        <div className="fw-semibold mb-2">{title}</div>
        {items.length ? (
          <ul className="small text-secondary mb-0 ps-3">
            {items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <div className="small text-secondary">No data yet.</div>
        )}
      </div>
    </div>
  )
}

function parseCsv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function preferredResumeModel(models: ModelSummary[]): string | undefined {
  return models.find((model) => model.id === 'llama-local-resume')?.id
    ?? models.find((model) => model.id === 'llama-local-general')?.id
    ?? undefined
}

function preferredTemplateModel(models: ModelSummary[]): string | undefined {
  return models.find((model) => model.id === 'llama-local-template')?.id
    ?? models.find((model) => model.id === 'llama-local-general')?.id
    ?? undefined
}

export default App
