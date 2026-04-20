import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'
import { api, getStoredApiKey, setStoredApiKey } from './api'
import type {
  AgentSummary,
  AuthStatusResponse,
  ApiKeyCreateResponse,
  ExecutionResponse,
  HealthResponse,
} from './types'

const INITIAL_CONTEXT = '{\n  "priority": "normal"\n}'

function App() {
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [history, setHistory] = useState<ExecutionResponse[]>([])
  const [authStatus, setAuthStatus] = useState<AuthStatusResponse | null>(null)
  const [apiKey, setApiKey] = useState(() => getStoredApiKey())
  const [bootstrapToken, setBootstrapToken] = useState('')
  const [bootstrapName, setBootstrapName] = useState('local-admin')
  const [bootstrapResult, setBootstrapResult] = useState<ApiKeyCreateResponse | null>(null)
  const [task, setTask] = useState('')
  const [agentName, setAgentName] = useState('')
  const [contextText, setContextText] = useState(INITIAL_CONTEXT)
  const [activeExecution, setActiveExecution] = useState<ExecutionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [bootError, setBootError] = useState('')
  const [submitError, setSubmitError] = useState('')

  async function loadProtectedData() {
    const [agentResult, historyResult] = await Promise.all([
      api.getAgents(),
      api.getExecutions(),
    ])
    setAgents(agentResult)
    setHistory(historyResult.executions)
  }

  useEffect(() => {
    let ignore = false

    async function bootstrap() {
      try {
        const healthResult = await api.getHealth()

        if (ignore) {
          return
        }

        setHealth(healthResult)
        const authResult = await api.getAuthStatus()
        if (ignore) {
          return
        }
        setAuthStatus(authResult)

        if (!authResult.auth_enabled || apiKey) {
          if (ignore) {
            return
          }
          await loadProtectedData()
        }
      } catch (error) {
        if (!ignore) {
          setBootError(
            error instanceof Error
              ? error.message
              : 'Unable to connect to the backend.',
          )
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
        context: parsedContext,
      })

      setActiveExecution(execution)
      setHistory((current) => [execution, ...current].slice(0, 10))
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : 'Task execution failed.',
      )
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
    <div className="app-shell">
      <header className="hero-panel">
        <div>
          <p className="eyebrow">Production-ready application base</p>
          <h1>Actypity Control Plane</h1>
          <p className="hero-copy">
            A scalable React and FastAPI baseline for multi-agent workflows,
            service health, and execution history.
          </p>
        </div>

        <div className="status-grid">
          <StatusCard
            label="API endpoint"
            value={api.baseUrl}
            tone="neutral"
          />
          <StatusCard
            label="Platform health"
            value={health?.status ?? 'unknown'}
            tone={health?.status === 'ok' ? 'good' : 'neutral'}
          />
          <StatusCard
            label="LLM mode"
            value={health?.llm_enabled ? 'enabled' : 'fallback'}
            tone={health?.llm_enabled ? 'good' : 'warn'}
          />
          <StatusCard
            label="Storage"
            value={health?.storage_backend ?? 'unknown'}
            tone="neutral"
          />
          <StatusCard
            label="Auth"
            value={
              health?.auth_enabled
                ? authStatus?.bootstrap_required
                  ? 'bootstrap required'
                  : apiKey
                    ? 'api key loaded'
                    : 'api key required'
                : 'disabled'
            }
            tone={
              !health?.auth_enabled
                ? 'neutral'
                : authStatus?.bootstrap_required
                  ? 'warn'
                  : apiKey
                    ? 'good'
                    : 'warn'
            }
          />
        </div>
      </header>

      <section className="panel auth-panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Access</p>
            <h2>Authentication</h2>
          </div>
        </div>

        <div className="stack-list">
          <label>
            <span>API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="Paste an admin, operator, or viewer API key"
            />
          </label>
          <button type="button" className="primary-button" onClick={handleLoadApiKey}>
            Load protected data
          </button>
          {health?.auth_enabled && authStatus?.bootstrap_required ? (
            <form className="compose-form" onSubmit={handleBootstrap}>
              <label>
                <span>Bootstrap token</span>
                <input
                  type="password"
                  value={bootstrapToken}
                  onChange={(event) => setBootstrapToken(event.target.value)}
                  placeholder="Enter BOOTSTRAP_ADMIN_TOKEN or SECRET_KEY"
                  required
                />
              </label>
              <label>
                <span>First admin key name</span>
                <input
                  type="text"
                  value={bootstrapName}
                  onChange={(event) => setBootstrapName(event.target.value)}
                  required
                />
              </label>
              <button type="submit" className="primary-button">
                Create first admin key
              </button>
            </form>
          ) : null}
          {bootstrapResult ? (
            <div className="result-card">
              <strong>Bootstrap complete</strong>
              <p>Admin key created for {bootstrapResult.name}.</p>
            </div>
          ) : null}
        </div>
      </section>

      {bootError ? (
        <section className="message-banner error">
          <strong>Backend connection failed.</strong>
          <span>{bootError}</span>
        </section>
      ) : null}

      <main className="content-grid">
        <section className="panel compose-panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Execution</p>
              <h2>Run a task</h2>
            </div>
            <span className="pill">{agents.length} agents loaded</span>
          </div>

          <form className="compose-form" onSubmit={handleSubmit}>
            <label>
              <span>Task</span>
              <textarea
                value={task}
                onChange={(event) => setTask(event.target.value)}
                placeholder="Describe the task or workflow you want the platform to execute."
                rows={6}
                required
              />
            </label>

            <div className="form-row">
              <label>
                <span>Preferred agent</span>
                <select
                  value={agentName}
                  onChange={(event) => setAgentName(event.target.value)}
                >
                  <option value="">Auto route</option>
                  {agents.map((agent) => (
                    <option key={agent.name} value={agent.name}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label>
              <span>Context JSON</span>
              <textarea
                value={contextText}
                onChange={(event) => setContextText(event.target.value)}
                rows={6}
                spellCheck={false}
              />
            </label>

            {submitError ? <p className="inline-error">{submitError}</p> : null}

            <button type="submit" className="primary-button" disabled={loading}>
              {loading ? 'Executing task...' : 'Execute task'}
            </button>
          </form>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Latest result</p>
              <h2>Execution output</h2>
            </div>
          </div>

          {activeExecution ? (
            <article className="result-card">
              <div className="result-meta">
                <span className="pill">{activeExecution.agent_name}</span>
                <span className="pill secondary">
                  {activeExecution.used_llm ? 'LLM-assisted' : 'deterministic'}
                </span>
              </div>
              <pre>{activeExecution.output}</pre>
            </article>
          ) : (
            <EmptyState
              title="No execution selected"
              description="Run a task to inspect the execution payload and agent response."
            />
          )}
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Registry</p>
              <h2>Available agents</h2>
            </div>
          </div>

          <div className="stack-list">
            {agents.map((agent) => (
              <article key={agent.name} className="list-card">
                <div className="list-card-header">
                  <h3>{agent.name}</h3>
                  <span className="pill secondary">
                    {agent.supports_tools ? 'tool-enabled' : 'core'}
                  </span>
                </div>
                <p>{agent.description}</p>
                <div className="tag-list">
                  {agent.capabilities.map((capability) => (
                    <span key={capability} className="tag">
                      {capability}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="panel wide-panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Audit trail</p>
              <h2>Recent executions</h2>
            </div>
          </div>

          {history.length ? (
            <div className="history-table">
              <div className="history-row history-head">
                <span>Execution</span>
                <span>Agent</span>
                <span>Status</span>
                <span>Mode</span>
              </div>
              {history.map((execution) => (
                <button
                  key={execution.execution_id}
                  type="button"
                  className="history-row"
                  onClick={() => setActiveExecution(execution)}
                >
                  <span>{execution.execution_id.slice(0, 8)}</span>
                  <span>{execution.agent_name}</span>
                  <span>{execution.status}</span>
                  <span>{execution.used_llm ? 'LLM' : 'fallback'}</span>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No executions yet"
              description="The execution history will appear here after the first task runs."
            />
          )}
        </section>
      </main>
    </div>
  )
}

type StatusCardProps = {
  label: string
  value: string
  tone: 'good' | 'warn' | 'neutral'
}

function StatusCard({ label, value, tone }: StatusCardProps) {
  return (
    <article className={`status-card tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

type EmptyStateProps = {
  title: string
  description: string
}

function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  )
}

export default App
