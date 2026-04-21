import { useEffect, useState } from 'react'

const displayError = (error: unknown) => {
  console.error(error)
}

export function PromptAdmin() {
  const [name, setName] = useState('')
  const [text, setText] = useState('')
  const [versions, setVersions] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [promptBody, setPromptBody] = useState<string>('')

  useEffect(() => {
    if (!name) return
    fetch(`/prompts/list?name=${encodeURIComponent(name)}`)
      .then((response) => response.json() as Promise<{ versions?: string[] }>)
      .then((data) => setVersions(data.versions || []))
      .catch(displayError)
  }, [name])

  const register = async () => {
    try {
      const res = await fetch('/prompts/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, text, meta: { source: 'admin' } }),
      })
      const j = await res.json()
      alert(`Registered ${String(j.version || '')}`)
      setName('')
      setText('')
    } catch (error) {
      displayError(error)
    }
  }

  const loadVersion = async (ver?: string) => {
    try {
      const url = `/prompts/get?name=${encodeURIComponent(name)}` + (ver ? `&version=${encodeURIComponent(ver)}` : '')
      const res = await fetch(url)
      const j = await res.json()
      setPromptBody(String(j.text || ''))
      setSelected(j.version ? String(j.version) : null)
    } catch (error) {
      displayError(error)
    }
  }

  return (
    <div className="card p-3">
      <h4>Prompt Registry (Dev)</h4>
      <div className="mb-2">
        <label className="form-label">Prompt name</label>
        <input className="form-control" value={name} onChange={(event) => setName(event.target.value)} />
      </div>
      <div className="mb-2">
        <label className="form-label">Versions</label>
        <select className="form-select" onChange={(event) => void loadVersion(event.target.value)}>
          <option value="">-- pick --</option>
          {versions.map((version) => <option key={version} value={version}>{version}</option>)}
        </select>
      </div>
      <div className="mb-2">
        <label className="form-label">Prompt text</label>
        <textarea className="form-control" rows={6} value={text} onChange={(event) => setText(event.target.value)} />
      </div>
      <div className="d-flex gap-2">
        <button className="btn btn-primary" onClick={() => void register()}>Register</button>
        <button className="btn btn-outline-secondary" onClick={() => void loadVersion()}>Load latest</button>
      </div>
      <hr />
      <h6>Loaded prompt ({selected})</h6>
      <pre style={{ whiteSpace: 'pre-wrap' }}>{promptBody}</pre>
    </div>
  )
}
export default PromptAdmin
