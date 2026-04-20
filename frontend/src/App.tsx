import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'
import { api, getStoredApiKey, setStoredApiKey } from './api'
import type {
  AgentSummary,
  ApiKeyCreateResponse,
  AuthStatusResponse,
  ExecutionResponse,
  HealthResponse,
  ModelSummary,
} from './types'

const INITIAL_CONTEXT = '{\n  "priority": "normal",\n  "channel": "web"\n}'

function App() {
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [models, setModels] = useState<ModelSummary[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [history, setHistory] = useState<ExecutionResponse[]>([])
  const [authStatus, setAuthStatus] = useState<AuthStatusResponse | null>(null)
  const [apiKey, setApiKey] = useState(() => getStoredApiKey())
  const [bootstrapToken, setBootstrapToken] = useState('')
  const [bootstrapName, setBootstrapName] = useState('local-admin')
  const [bootstrapResult, setBootstrapResult] = useState<ApiKeyCreateResponse | null>(null)
  const [task, setTask] = useState('')
  const [agentName, setAgentName] = useState('')
  const [modelProfile, setModelProfile] = useState('')
  const [contextText, setContextText] = useState(INITIAL_CONTEXT)
  const [activeExecution, setActiveExecution] = useState<ExecutionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [bootError, setBootError] = useState('')
  const [submitError, setSubmitError] = useState('')

  async function loadProtectedData() {
    const [agentResult, modelResult, historyResult] = await Promise.all([
      api.getAgents(),
      api.getModels(),
      api.getExecutions(),
    ])
    setAgents(agentResult)
    setModels(modelResult.models)
    setHistory(historyResult.executions)
  }

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
  }, [apiKey])

  useEffect(() => {
    setStoredApiKey(apiKey)
  }, [apiKey])

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.name === agentName) ?? null,
    [agents, agentName],
  )

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitError('')
    setLoading(true)

    try {
      const parsedContext = contextText.trim()
        ? (JSON.parse(contextText) as Record<string, unknown>)
        : {}
      const execution = await api.executeTask({
        task,
        agent_name: agentName || undefined,
        model_profile: modelProfile || undefined,
        context: parsedContext,
      })

      setActiveExecution(execution)
      setHistory((current) => [execution, ...current].slice(0, 10))
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : 'Task execution failed.')
    } finally {
      setLoading(false)
    }
  }

  async function handleBootstrap(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBootError('')
    try {
      const created = await api.bootstrapAdminKey(bootstrapToken, bootstrapName)
      setBootstrapResult(created)
      setStoredApiKey(created.key)
      setApiKey(created.key)
      const authResult = await api.getAuthStatus()
      setAuthStatus(authResult)
      await loadProtectedData()
    } catch (error) {
      setBootError(error instanceof Error ? error.message : 'Bootstrap failed.')
    }
  }

  async function handleLoadApiKey() {
    setBootError('')
    try {
      setStoredApiKey(apiKey)
      const authResult = await api.getAuthStatus()
      setAuthStatus(authResult)
      await loadProtectedData()
    } catch (error) {
      setBootError(error instanceof Error ? error.message : 'Failed to load data with the API key.')
    }
  }

  return (
    <div className="app-page">
      <nav className="navbar navbar-expand-lg border-bottom bg-white bg-opacity-75 backdrop-blur sticky-top">
        <div className="container py-2">
          <span className="navbar-brand fw-semibold mb-0 h1">Antypity</span>
          <span className="badge rounded-pill text-bg-primary">Bootstrap control plane</span>
        </div>
      </nav>

      <div className="container py-5">
        <section className="hero-gradient rounded-5 text-white p-4 p-lg-5 shadow-lg mb-4">
          <div className="row g-4 align-items-center">
            <div className="col-lg-7">
              <div className="text-uppercase small fw-semibold opacity-75 mb-2">Multi-agent, multi-model platform</div>
              <h1 className="display-4 fw-bold mb-3">Modern orchestration, Bootstrap UI, API-driven execution.</h1>
              <p className="lead mb-0 opacity-90">
                The frontend now exposes agent and model orchestration controls, while the backend routes
                orchestration through internal APIs instead of direct function invocation.
              </p>
            </div>
            <div className="col-lg-5">
              <div className="row g-3">
                <StatusTile label="API endpoint" value={api.baseUrl} />
                <StatusTile label="Health" value={health?.status ?? 'unknown'} />
                <StatusTile label="Auth" value={authStatus?.bootstrap_required ? 'bootstrap required' : apiKey ? 'api key loaded' : 'key required'} />
                <StatusTile label="Models" value={models.length ? `${models.length} profiles` : 'not loaded'} />
              </div>
            </div>
          </div>
        </section>

        {bootError ? (
          <div className="alert alert-danger shadow-sm" role="alert">
            <strong>Connection error.</strong> {bootError}
          </div>
        ) : null}

        <div className="row g-4">
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
                  <label className="form-label">API key</label>
                  <input
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
                      <label className="form-label">Bootstrap token</label>
                      <input
                        className="form-control"
                        type="password"
                        value={bootstrapToken}
                        onChange={(event) => setBootstrapToken(event.target.value)}
                        placeholder="BOOTSTRAP_ADMIN_TOKEN or SECRET_KEY"
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">First admin key name</label>
                      <input
                        className="form-control"
                        type="text"
                        value={bootstrapName}
                        onChange={(event) => setBootstrapName(event.target.value)}
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
            <div className="card glass-card border-0 rounded-4">
              <div className="card-body p-4">
                <div className="d-flex justify-content-between align-items-start mb-4">
                  <div>
                    <div className="text-uppercase small text-secondary fw-semibold">Execution</div>
                    <h2 className="section-title h4 mb-1">Multi-agent orchestration console</h2>
                    <p className="text-secondary mb-0">
                      Select a specific agent/model pair or let the backend route the task through its internal orchestration APIs.
                    </p>
                  </div>
                </div>

                <form onSubmit={handleSubmit}>
                  <div className="mb-3">
                    <label className="form-label">Task</label>
                    <textarea
                      className="form-control"
                      rows={4}
                      value={task}
                      onChange={(event) => setTask(event.target.value)}
                      placeholder="Describe the task, issue, or workflow objective"
                      required
                    />
                  </div>

                  <div className="row g-3">
                    <div className="col-md-6">
                      <label className="form-label">Agent</label>
                      <select
                        className="form-select"
                        value={agentName}
                        onChange={(event) => setAgentName(event.target.value)}
                      >
                        <option value="">Auto-route across agents</option>
                        {agents.map((agent) => (
                          <option key={agent.name} value={agent.name}>
                            {agent.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="col-md-6">
                      <label className="form-label">Model profile</label>
                      <select
                        className="form-select"
                        value={modelProfile}
                        onChange={(event) => setModelProfile(event.target.value)}
                      >
                        <option value="">Use agent default model</option>
                        {models.map((model) => (
                          <option key={model.id} value={model.id}>
                            {model.id} · {model.provider}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="mt-3">
                    <label className="form-label">Context JSON</label>
                    <textarea
                      className="form-control code-block"
                      rows={6}
                      value={contextText}
                      onChange={(event) => setContextText(event.target.value)}
                    />
                  </div>

                  {selectedAgent ? (
                    <div className="alert alert-light border mt-3 mb-0">
                      <div className="fw-semibold mb-1">{selectedAgent.name}</div>
                      <div className="text-secondary small mb-2">{selectedAgent.description}</div>
                      <div className="d-flex flex-wrap gap-2">
                        {selectedAgent.capabilities.map((capability) => (
                          <span key={capability} className="badge text-bg-light border">
                            {capability}
                          </span>
                        ))}
                        {selectedAgent.preferred_model ? (
                          <span className="badge text-bg-primary">
                            preferred model: {selectedAgent.preferred_model}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  ) : null}

                  {submitError ? (
                    <div className="alert alert-danger mt-3 mb-0" role="alert">
                      {submitError}
                    </div>
                  ) : null}

                  <div className="d-flex flex-wrap gap-2 mt-4">
                    <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
                      {loading ? 'Running orchestration...' : 'Execute task'}
                    </button>
                    <span className="badge metric-pill rounded-pill px-3 py-2 align-self-center text-secondary">
                      {models.length} model profiles available
                    </span>
                  </div>
                </form>
              </div>
            </div>
          </div>

          <div className="col-lg-6">
            <div className="card glass-card border-0 rounded-4 h-100">
              <div className="card-body p-4">
                <div className="d-flex justify-content-between align-items-start mb-3">
                  <div>
                    <div className="text-uppercase small text-secondary fw-semibold">Latest result</div>
                    <h2 className="section-title h4 mb-0">Execution output</h2>
                  </div>
                </div>
                {activeExecution ? (
                  <>
                    <div className="d-flex flex-wrap gap-2 mb-3">
                      <span className="badge text-bg-primary">{activeExecution.agent_name}</span>
                      <span className="badge text-bg-light border">{activeExecution.model_profile ?? 'agent default'}</span>
                      <span className="badge text-bg-light border">{activeExecution.provider ?? 'unknown provider'}</span>
                    </div>
                    <pre className="code-block bg-body-tertiary rounded-4 p-3 mb-0">
                      {activeExecution.output}
                    </pre>
                  </>
                ) : (
                  <div className="text-secondary">
                    Run a task to inspect the orchestrated output, selected agent, and chosen model profile.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="col-lg-6">
            <div className="card glass-card border-0 rounded-4 h-100">
              <div className="card-body p-4">
                <div className="d-flex justify-content-between align-items-start mb-3">
                  <div>
                    <div className="text-uppercase small text-secondary fw-semibold">Catalog</div>
                    <h2 className="section-title h4 mb-0">Available model profiles</h2>
                  </div>
                </div>
                <div className="row g-3">
                  {models.map((model) => (
                    <div key={model.id} className="col-md-6">
                      <div className="border rounded-4 p-3 h-100 bg-white">
                        <div className="fw-semibold">{model.id}</div>
                        <div className="small text-secondary">{model.provider} · {model.mode}</div>
                        <div className="small mt-2 text-secondary">{model.description}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="col-12">
            <div className="card glass-card border-0 rounded-4">
              <div className="card-body p-4">
                <div className="d-flex justify-content-between align-items-start mb-3">
                  <div>
                    <div className="text-uppercase small text-secondary fw-semibold">History</div>
                    <h2 className="section-title h4 mb-0">Recent executions</h2>
                  </div>
                </div>
                <div className="table-wrap">
                  <table className="table align-middle">
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
                      {history.map((execution) => (
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

export default App
