import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { ChatMessage } from './types'

const SESSION_KEY = 'actypity_chat_session'

function getSessionId(): string {
  let id = window.sessionStorage.getItem(SESSION_KEY)
  if (!id) {
    id = `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    window.sessionStorage.setItem(SESSION_KEY, id)
  }
  return id
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [resumeText, setResumeText] = useState('')
  const [jdText, setJdText] = useState('')
  const [sessionId] = useState(() => getSessionId())
  const [provider, setProvider] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Load history on mount
    api.getChatHistory(sessionId).then(h => setMessages(h.messages)).catch(() => {})
  }, [sessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend() {
    if (!input.trim() || loading) return
    const userMsg: ChatMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const resp = await api.chat({
        message: input,
        session_id: sessionId,
        resume_text: resumeText || undefined,
        jd_text: jdText || undefined,
      })
      setProvider(resp.provider)
      setMessages(prev => [...prev, { role: 'assistant', content: resp.response }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${err instanceof Error ? err.message : 'Chat failed. Is the backend running?'}`,
      }])
    } finally {
      setLoading(false)
    }
  }

  async function handleClear() {
    await api.clearChatSession(sessionId).catch(() => {})
    setMessages([])
  }

  const suggestions = [
    'How can I improve my resume for a senior engineer role?',
    'What ATS keywords should I add for a data science position?',
    'Review my resume summary and suggest improvements',
    'What salary range should I expect for 5 years of experience?',
    'Help me prepare for a system design interview',
    'Which resume template is best for a startup environment?',
  ]

  return (
    <div className="row g-4">
      <div className="col-lg-8">
        <div className="card glass-card border-0 rounded-4 h-100">
          <div className="card-body p-4 d-flex flex-column" style={{ minHeight: '600px' }}>
            <div className="d-flex justify-content-between align-items-center mb-3">
              <div>
                <div className="text-uppercase small text-secondary fw-semibold">AI Assistant</div>
                <h2 className="section-title h4 mb-0">Career Coach Chatbot</h2>
              </div>
              <div className="d-flex gap-2 align-items-center">
                {provider && (
                  <span className="badge bg-secondary small">{provider}</span>
                )}
                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={handleClear}>
                  Clear
                </button>
              </div>
            </div>

            {/* Messages */}
            <div
              className="flex-grow-1 overflow-auto border rounded-4 p-3 bg-light mb-3"
              style={{ maxHeight: '420px' }}
            >
              {messages.length === 0 && (
                <div className="text-secondary text-center py-5">
                  <div className="fs-1 mb-2">💬</div>
                  <div>Ask me anything about your resume, job search, or career!</div>
                  <div className="mt-3 d-flex flex-wrap gap-2 justify-content-center">
                    {suggestions.slice(0, 3).map((s, i) => (
                      <button
                        key={i}
                        type="button"
                        className="btn btn-sm btn-outline-primary"
                        onClick={() => { setInput(s); }}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`d-flex mb-3 ${msg.role === 'user' ? 'justify-content-end' : 'justify-content-start'}`}
                >
                  <div
                    className={`rounded-4 px-3 py-2 ${msg.role === 'user' ? 'bg-primary text-white' : 'bg-white border'}`}
                    style={{ maxWidth: '80%', whiteSpace: 'pre-wrap' }}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="d-flex justify-content-start mb-3">
                  <div className="rounded-4 px-3 py-2 bg-white border text-secondary fst-italic">
                    Thinking…
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="d-flex gap-2">
              <input
                type="text"
                className="form-control"
                placeholder="Ask about your resume, templates, job search…"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                disabled={loading}
              />
              <button
                type="button"
                className="btn btn-primary px-4"
                onClick={handleSend}
                disabled={loading || !input.trim()}
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="col-lg-4">
        <div className="card glass-card border-0 rounded-4 mb-4">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold mb-2">Context</div>
            <div className="mb-3">
              <label className="form-label small fw-semibold">Resume Text (optional)</label>
              <textarea
                className="form-control form-control-sm"
                rows={4}
                placeholder="Paste your resume text here for personalised advice…"
                value={resumeText}
                onChange={e => setResumeText(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label small fw-semibold">Job Description (optional)</label>
              <textarea
                className="form-control form-control-sm"
                rows={3}
                placeholder="Paste a job description to match advice to the role…"
                value={jdText}
                onChange={e => setJdText(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="card glass-card border-0 rounded-4">
          <div className="card-body p-4">
            <div className="text-uppercase small text-secondary fw-semibold mb-2">Quick Questions</div>
            <div className="d-flex flex-column gap-2">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  type="button"
                  className="btn btn-sm btn-outline-secondary text-start"
                  onClick={() => setInput(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
