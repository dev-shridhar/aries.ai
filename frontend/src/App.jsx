import { useState, useEffect, useCallback } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { python } from '@codemirror/lang-python'
import { vscodeDark } from '@uiw/codemirror-theme-vscode'
import { indentUnit } from '@codemirror/language'
import { keymap } from '@codemirror/view'
import { indentWithTab } from '@codemirror/commands'
import VoiceAgent from './VoiceAgent'
import './index.css'

function App() {
  const [view, setView] = useState('home')
  const [problem, setProblem] = useState(null)
  const [code, setCode] = useState('class Solution:\n    def solve(self):\n        pass')
  const [problems, setProblems] = useState([])
  const [search, setSearch] = useState('')
  const [diff, setDiff] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [toasts, setToasts] = useState([])

  const toast = useCallback((msg, type = 'info') => {
    const id = Date.now()
    setToasts(p => [...p, { id, msg, type }])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3000)
  }, [])

  const fetchProblems = useCallback(async (q = '', d = '') => {
    setLoading(true)
    try {
      const p = new URLSearchParams({ limit: '50' })
      if (q) p.set('q', q)
      if (d) p.set('difficulty', d)
      const res = await fetch('/api/problems?' + p)
      if (res.ok) setProblems((await res.json()).problems || [])
    } catch { setProblems([]) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (view === 'problems' && !problems.length) fetchProblems()
  }, [view])

  const loadProblem = async (slug) => {
    setProblem(null)
    setResults([])
    try {
      const res = await fetch(`/api/problems/${slug}`)
      if (!res.ok) { toast('Failed to load problem', 'info'); return }
      const p = await res.json()
      setProblem(p)
      setCode(p.stub || 'class Solution:\n    def solve(self):\n        pass')
      setView('solve')
    } catch { toast('Failed to load problem', 'info') }
  }

  const handleRun = async () => {
    if (!problem) return
    setLoading(true)
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, slug: problem.slug, examples: problem.examples, expected: problem.expected })
      })
      const data = await res.json()
      setResults(data.results || [])
    } catch { setResults([{ error: 'Run failed' }]) }
    finally { setLoading(false) }
  }

  return (
    <>
      {view === 'home' && (
        <div id="home-view">
          <div className="hero-title">aries.ai</div>
          <div className="hero-subtitle">voice dsa tutor</div>
          <div className="feature-blocks">
            <div className="feature-card" onClick={() => setView('problems')}>
              <h3>Solve with Me</h3>
              <p>Talk through LeetCode problems with an AI companion by your side.</p>
            </div>
          </div>
        </div>
      )}

      {view === 'problems' && (
        <div id="problems-view">
          <header>
            <div className="nav-left">
              <h1 onClick={() => setView('home')}>aries<span>.ai</span></h1>
              <button className={`nav-btn active`}>Problems</button>
            </div>
          </header>
          <div className="problems-container">
            <div className="problems-header">
              <h2>Problems</h2>
              <div className="problems-filters">
                <input placeholder="Search..." value={search} onChange={e => { setSearch(e.target.value); fetchProblems(e.target.value, diff) }} />
                <select value={diff} onChange={e => { setDiff(e.target.value); fetchProblems(search, e.target.value) }}>
                  <option value="">All</option>
                  <option value="EASY">Easy</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HARD">Hard</option>
                </select>
              </div>
            </div>
            <div className="problems-list">
              {loading ? <div style={{ color: 'var(--muted)', padding: 20 }}>Loading...</div> :
                problems.map(p => (
                  <div key={p.slug} className="problem-list-item" onClick={() => loadProblem(p.slug)}>
                    <div className="problem-list-info">
                      <h3>{p.title}</h3>
                      <div className="problem-tags">
                        {(p.topics || []).slice(0, 3).map(t => <span key={t} className="tag">{t}</span>)}
                      </div>
                    </div>
                    <span className={`difficulty ${p.difficulty}`}>{p.difficulty}</span>
                  </div>
                ))
              }
            </div>
          </div>
        </div>
      )}

      {view === 'solve' && (
        <div id="solve-view">
          <header>
            <div className="nav-left">
              <h1 onClick={() => setView('home')}>aries<span>.ai</span></h1>
              <button className="nav-btn" onClick={() => setView('problems')}>Problems</button>
              <button className="nav-btn active">Solve</button>
            </div>
            <div className="nav-right">
              {problem && <button className="btn-today" onClick={handleRun} disabled={loading}>{loading ? '...' : 'Run'}</button>}
            </div>
          </header>
          <div className="three-col">
            <div className="panel panel-problem">
              <div className="panel-header"><h2>Problem</h2></div>
              <div className="panel-body">
                {problem ? (
                  <div id="problem-statement">
                    <div className="problem-title">{problem.title}</div>
                    {problem.difficulty && <span className={`difficulty ${problem.difficulty}`}>{problem.difficulty}</span>}
                    <div className="problem-content" dangerouslySetInnerHTML={{ __html: problem.content || '' }} />
                  </div>
                ) : (
                  <p style={{ color: 'var(--muted)' }}>Search and load a problem to get started.</p>
                )}
              </div>
            </div>
            <div className="panel panel-code">
              <div className="panel-header"><h2>Code</h2></div>
              <div className="panel-body" style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ flex: 1 }}>
                  <CodeMirror
                    value={code}
                    height="100%"
                    theme={vscodeDark}
                    extensions={[python(), indentUnit.of("    "), keymap.of([indentWithTab])]}
                    onChange={v => setCode(v)}
                  />
                </div>
                {results.length > 0 && (
                  <div className="test-results">
                    <h4>Results</h4>
                    <div className="test-cases">
                      {results.map((r, i) => (
                        <div key={i} className={`test-case ${r.error ? '' : r.passed ? 'passed' : 'failed'}`}>
                          {r.error ? <p className="error">{r.error}</p> : (
                            <>
                              <div className="test-case-header">
                                <span>Case {i + 1}</span>
                                <span className="test-case-status">{r.passed ? 'Passed' : 'Failed'}</span>
                              </div>
                              <div className="test-case-info">
                                {r.input && <div><strong>Input:</strong> <code>{r.input}</code></div>}
                                {r.output && <div><strong>Output:</strong> <code>{r.output}</code></div>}
                                {r.expected && <div><strong>Expected:</strong> <code>{r.expected}</code></div>}
                              </div>
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <VoiceAgent currentCode={code} />

      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`} onClick={() => setToasts(p => p.filter(x => x.id !== t.id))}>{t.msg}</div>
        ))}
      </div>
    </>
  )
}

export default App
