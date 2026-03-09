import { useState, useEffect, useRef } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { python } from '@codemirror/lang-python'
import { vscodeDark } from '@uiw/codemirror-theme-vscode'
import './index.css'

function App() {
  const [view, setView] = useState('home')
  const [currentProblem, setCurrentProblem] = useState(null)
  const [currentProblemSlug, setCurrentProblemSlug] = useState('')
  const [code, setCode] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [problemsList, setProblemsList] = useState([])
  const [isProblemsLoading, setIsProblemsLoading] = useState(false)
  const [testResults, setTestResults] = useState([])
  const [showTestResults, setShowTestResults] = useState(false)
  const [selectedDifficulty, setSelectedDifficulty] = useState('')
  const [isAriesTalking, setIsAriesTalking] = useState(false)
  const [ariesBubble, setAriesBubble] = useState('')
  const [showAriesBubble, setShowAriesBubble] = useState(false)
  const [toasts, setToasts] = useState([])
  const codeEditorRef = useRef(null)

  const fetchProblemsList = async (query = '', diff = '') => {
    setIsProblemsLoading(true)
    try {
      const params = new URLSearchParams({ limit: '50' })
      if (query) params.set('q', query)
      if (diff) params.set('difficulty', diff)
      const res = await fetch('/api/search?' + params)
      if (res.ok) {
        const data = await res.json()
        setProblemsList(data.problems || [])
      }
    } catch {
      setProblemsList([])
    } finally {
      setIsProblemsLoading(false)
    }
  }

  useEffect(() => {
    if (view === 'problems' && problemsList.length === 0) {
      fetchProblemsList()
    }
  }, [view])

  const addToast = (message, type = 'info') => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 3000)
  }

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  useEffect(() => {
    setTimeout(() => {
      if (view === 'home') {
        setAriesBubble("An O(n) solution today keeps the TLE away! Ready to optimize your logic?")
        setShowAriesBubble(true)
        setTimeout(() => setShowAriesBubble(false), 4000)
      }
    }, 2000)
  }, [view])


  const loadProblem = async (slug) => {
    let targetSlug = slug;
    setCurrentProblemSlug(targetSlug)
    setCurrentProblem(null)
    setTestResults([])
    setShowTestResults(false)

    try {
      if (slug === 'daily-challenge') {
        const dailyRes = await fetch('/api/daily')
        if (dailyRes.ok) {
          const dailyData = await dailyRes.json()
          targetSlug = dailyData.slug
          setCurrentProblemSlug(targetSlug)
        }
      }

      const res = await fetch('/api/problem/' + encodeURIComponent(targetSlug))
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        setCurrentProblem({ error: err.detail || res.statusText || 'Failed to load' })
        return
      }
      const p = await res.json()
      setCurrentProblem(p)
      setCode(p.pythonStub || '# Write your solution\nclass Solution:\n    def solve(self):\n        pass')
      setView('solve')
      explainProblemToAgent(p, slug)
    } catch {
      setCurrentProblem({ error: 'Failed to load problem' })
    }
  }

  const explainProblemToAgent = async (problem, slug) => {
    const title = problem.title || slug
    try {
      const res = await fetch('/api/explain-problem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, slug }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        return
      }
    } catch {
      console.error('Failed to explain problem')
    }
  }





  const handleRun = async () => {
    if (!currentProblem?.exampleTestcases) {
      setShowTestResults(true)
      setTestResults([{ error: 'No example test cases found for this problem.' }])
      return
    }

    setTestResults([])
    setShowTestResults(true)

    try {
      const res = await fetch('/api/run-examples', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          examples: currentProblem.exampleTestcases,
          expected_outputs: currentProblem.expectedOutputs,
          public_cases_count: currentProblem.expectedOutputs.length,
          order_independent: currentProblem.orderIndependent
        }),
      })
      const data = await res.json().catch(() => ({}))

      if (!res.ok) {
        setTestResults([{ error: data.detail || res.statusText || 'Execution failed' }])
        return
      }

      setTestResults(data.results || [])
      if (data.results && data.results.length > 0) {
        analyzeSubmission(code, currentProblemSlug, data.results, data.stderr || "", 1)
      }
    } catch {
      setTestResults([{ error: 'Request failed' }])
    }
  }

  const handleSubmit = async () => {
    if (!currentProblemSlug) {
      setShowTestResults(true)
      setTestResults([{ error: 'No problem context found.' }])
      return
    }

    setTestResults([])
    setShowTestResults(true)

    try {
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          slug: currentProblemSlug
        }),
      })
      const data = await res.json().catch(() => ({}))

      if (!res.ok) {
        setTestResults([{ error: data.detail || res.statusText || 'Submission failed' }])
        return
      }

      setTestResults(data.results || [])
      const resultsArray = data.results || []
      const allPassed = resultsArray.length > 0 && resultsArray.every(r => r.passed)
      analyzeSubmission(code, currentProblemSlug, resultsArray, data.stderr || "", allPassed ? 3 : 1)
    } catch {
      setTestResults([{ error: 'Request failed' }])
    }
  }

  const analyzeSubmission = async (code, slug, results, stderr, level = 1) => {
    try {
      const res = await fetch('/api/analyze-submission', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, slug, results, stderr, level }),
      })
      const data = await res.json().catch(() => ({}))

      if (res.ok && data.response) {
        const resultsPassed = results.length > 0 && results.every(r => r.passed && r.verified !== false)
        return resultsPassed
      } else {
        return false
      }
    } catch {
      return false
    }
  }

  const speakAries = async (forcedText = null) => {
    if (isAriesTalking) return
    setIsAriesTalking(true)

    try {
      let message = forcedText || "I'm here to help you conquer coding challenges!"

      setAriesBubble(message)
      setShowAriesBubble(true)

      const ttsRes = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: message })
      })

      if (!ttsRes.ok) throw new Error("TTS failed")

      const audioBlob = await ttsRes.blob()
      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)

      audio.onended = () => {
        setIsAriesTalking(false)
        setTimeout(() => {
          setShowAriesBubble(false)
        }, 6000)
      }

      await audio.play()
    } catch {
      console.error("Aries Error: TTS failed")
      setAriesBubble("Oops, my voice circuits are on break! But I'm still cheering for you!")
      setIsAriesTalking(false)
      setTimeout(() => setShowAriesBubble(false), 5000)
    }
  }

  const handleHomeSearch = async (query) => {
    setSearchQuery(query)
    if (!query.trim()) {
      setSearchResults([])
      return
    }

    try {
      const res = await fetch('/api/search?q=' + encodeURIComponent(query) + '&limit=10')
      if (res.ok) {
        const data = await res.json()
        setSearchResults(data.problems || [])
      }
    } catch {
      setSearchResults([])
    }
  }

  const handleTaskbarSearch = async (query, difficulty) => {
    if (!query && !difficulty) {
      setSearchResults([])
      return
    }

    try {
      const params = new URLSearchParams({ limit: '15' })
      if (query) params.set('q', query)
      if (difficulty) params.set('difficulty', difficulty)
      const res = await fetch('/api/search?' + params)
      if (!res.ok) throw new Error("Search failed")
      const data = await res.json()
      setSearchResults(data.problems || [])
    } catch {
      setSearchResults([])
    }
  }

  const getDifficultyClass = (difficulty) => {
    if (!difficulty) return ''
    return difficulty.toLowerCase().replace(/^\w/, c => c.toUpperCase())
  }

  const parseMarkdown = (text) => {
    if (!text) return ''

    let cleanText = text.trim()
    const codeBlocks = []

    cleanText = cleanText.replace(/```([a-z]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
      const id = `__CODE_BLOCK_${codeBlocks.length}__`
      codeBlocks.push(`<pre><code>${code.trim()}</code></pre>`)
      return id
    })

    cleanText = cleanText.replace(/^\[([A-Z_ ]{3,})\]\s*:?/gm, '[$1]')

    const rawSections = cleanText.split(/\n(?=\[[A-Z_ ]{3,}\])/g)

    let finalHtml = rawSections
      .filter(s => s.trim().length > 0)
      .map(s => {
        let content = s.trim()
        let header = ''

        const headerMatch = content.match(/^\[([A-Z_ ]{3,})\]/)
        if (headerMatch) {
          header = headerMatch[1].trim()
          content = content.replace(/^\[[A-Z_ ]{3,}\]\s*:?/, '').trim()
        }

        let sectionHtml = content
          .replace(/\*\*([\s\S]*?)\*\*/g, '<strong>$1</strong>')
          .replace(/`([^`]+)`/g, '<code>$1</code>')
          .replace(/^\s*[*\-•]\s+(.*)$/gm, '<li>$1</li>')
          .replace(/^\s*\d+\.\s*(.*)$/gm, '<li>$1</li>')
          .replace(/\n/g, '<br>')

        if (sectionHtml.includes('<li>')) {
          sectionHtml = sectionHtml.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
            .replace(/<\/li><br>/g, '</li>')
        }

        if (header) {
          return `<div class="bot-section"><div class="bot-header">${header}</div><div class="bot-content">${sectionHtml}</div></div>`
        }
        return `<div class="bot-section"><div class="bot-content">${sectionHtml}</div></div>`
      }).join('')

    codeBlocks.forEach((html, i) => {
      finalHtml = finalHtml.split(`__CODE_BLOCK_${i}__`).join(html)
    })

    return finalHtml
  }

  const handleCodeKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      handleRun()
      return
    }

    if (e.key === 'Tab') {
      e.preventDefault()
      const start = e.target.selectionStart
      const end = e.target.selectionEnd
      const insert = '    '
      setCode(code.slice(0, start) + insert + code.slice(end))
      setTimeout(() => {
        if (codeEditorRef.current) {
          codeEditorRef.current.selectionStart = codeEditorRef.current.selectionEnd = start + insert.length
        }
      }, 0)
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      const value = code
      const start = e.target.selectionStart
      const lineStart = value.lastIndexOf('\n', start - 1)
      const actualLineStart = lineStart === -1 ? 0 : lineStart + 1
      const line = value.slice(actualLineStart, start)
      const indentMatch = line.match(/^[\t ]*/)
      let indent = indentMatch ? indentMatch[0] : ''

      if (line.trim().endsWith(':')) {
        indent += '    '
      }

      e.preventDefault()
      const insert = '\n' + indent
      setCode(code.slice(0, start) + insert + code.slice(start))
      setTimeout(() => {
        if (codeEditorRef.current) {
          codeEditorRef.current.selectionStart = codeEditorRef.current.selectionEnd = start + insert.length
        }
      }, 0)
    }
  }

  return (
    <>
      {view === 'home' ? (
        <div id="home-view">
          <div className="hero-logo">
            <img src="/logo.png" alt="Aries Brand" />
          </div>
          <h1 className="hero-title">aries.ai</h1>
          <p className="hero-subtitle">Elevate Your Algorithmic Intelligence</p>

          <div className="feature-blocks">
            <div
              className="feature-card card-learn"
              style={{ opacity: 0.6, cursor: 'not-allowed', position: 'relative' }}
              onClick={() => {
                setAriesBubble("The learning modules are being refined for a more premium experience. Stay tuned!")
                setShowAriesBubble(true)
                setTimeout(() => setShowAriesBubble(false), 5000)
              }}
            >
              <img src="/learn_card.png" className="icon" alt="Learn" />
              <div style={{ position: 'absolute', top: 10, right: 10, background: '#8b5cf6', color: 'white', padding: '2px 8px', borderRadius: 12, fontSize: '0.6rem', fontWeight: 'bold', boxShadow: '0 0 10px rgba(139, 92, 246, 0.4)' }}>
                COMING SOON</div>
              <h3>Learn with Me</h3>
              <p>Master complex patterns through guided architectural deep-dives and rhythmic logic.</p>
            </div>
            <div
              className="feature-card card-solve"
              onClick={() => setView('solve')}
            >
              <img src="/solve_card.png" className="icon" alt="Solve" />
              <h3>Solve with Me</h3>
              <p>Elevate your execution with a real-time AI companion on live algorithmic challenges.</p>
            </div>
          </div>
        </div>
      ) : view === 'problems' ? (
        <div id="problems-view">
          <header>
            <div className="nav-left">
              <div className="logo-wrap" onClick={() => setView('home')} title="Return to Home">
                <h1>aries<span>.ai</span></h1>
              </div>
              <nav className="header-nav">
                <button className={`nav-btn ${view === 'problems' ? 'active' : ''}`} onClick={() => setView('problems')}>Problems</button>
                <button className={`nav-btn ${view === 'solve' ? 'active' : ''}`} onClick={() => { if (currentProblem) setView('solve'); else loadProblem('daily-challenge'); }}>Solve</button>
              </nav>
            </div>
            <div className="nav-right">
              <button type="button" className="btn-today" onClick={() => loadProblem('daily-challenge')}>
                Today's challenge
              </button>
            </div>
          </header>
          <div className="problems-container">
            <div className="problems-header">
              <h2>Problem Set</h2>
              <div className="problems-filters">
                <input
                  type="text"
                  placeholder="Search problems…"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value)
                    fetchProblemsList(e.target.value, selectedDifficulty)
                  }}
                  className="problems-search-input"
                />
                <select
                  value={selectedDifficulty}
                  onChange={(e) => {
                    setSelectedDifficulty(e.target.value)
                    fetchProblemsList(searchQuery, e.target.value)
                  }}
                  className="problems-diff-select"
                >
                  <option value="">Any Difficulty</option>
                  <option value="EASY">Easy</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HARD">Hard</option>
                </select>
              </div>
            </div>

            <div className="problems-list">
              {isProblemsLoading ? (
                <div className="problems-loading">Loading problems...</div>
              ) : problemsList.length > 0 ? (
                problemsList.map(p => (
                  <div key={p.titleSlug || p.slug} className="problem-list-item" onClick={() => loadProblem(p.titleSlug || p.slug)}>
                    <div className="problem-list-info">
                      <h3>{p.title}</h3>
                      <div className="problem-tags">
                        {(p.topicTags || []).slice(0, 3).map(t => (
                          <span key={t.slug || t} className="tag">{t.name || t}</span>
                        ))}
                      </div>
                    </div>
                    <span className={`difficulty ${getDifficultyClass(p.difficulty)}`}>{p.difficulty}</span>
                  </div>
                ))
              ) : (
                <div className="problems-empty">No problems found matching your criteria.</div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div id="solve-view">
          <div className={`drawer-overlay ${agentDrawerOpen ? 'show' : ''}`} onClick={() => setAgentDrawerOpen(false)}></div>

          <header>
            <div className="nav-left">
              <div className="logo-wrap" onClick={() => setView('home')} title="Return to Home">
                <div className={`aries-avatar mini ${isAriesTalking ? 'talking' : ''}`}>
                  <img src="/logo.png" alt="Aries" />
                </div>
                <h1>aries<span>.ai</span></h1>
              </div>
              <nav className="header-nav">
                <button className={`nav-btn ${view === 'problems' ? 'active' : ''}`} onClick={() => setView('problems')}>Problems</button>
                <button className={`nav-btn ${view === 'solve' ? 'active' : ''}`} onClick={() => setView('solve')}>Solve</button>
              </nav>
            </div>
            <div className="nav-right">
              <button type="button" className="btn-today" onClick={() => loadProblem('daily-challenge')}>
                Today's challenge
              </button>
            </div>
          </header>


          <div className="three-col">
            <div className="panel panel-problem">
              <div className="panel-header">
                <h2>Problem</h2>
                <div className="panel-metadata">
                  <span>{currentProblem?.difficulty}</span>
                </div>
              </div>
              <div className="panel-body">
                {currentProblem?.error ? (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{currentProblem.error}</p>
                ) : currentProblem ? (
                  <div id="problem-statement">
                    <div className="problem-title">{currentProblem.title}</div>
                    {currentProblem.difficulty && (
                      <span className={`difficulty ${getDifficultyClass(currentProblem.difficulty)}`}>
                        {currentProblem.difficulty}
                      </span>
                    )}
                    <div className="problem-content" dangerouslySetInnerHTML={{ __html: currentProblem.content || '' }} />
                  </div>
                ) : (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    Enter a problem slug in the header (e.g. two-sum) and click Go, or ask the agent to open one.
                  </p>
                )}
              </div>
            </div>

            <div className="panel panel-code">
              <div className="panel-header">
                <h2>Code</h2>
              </div>
              <div className="panel-body" style={{ display: 'flex', flexDirection: 'column' }}>
                <div className="code-toolbar" style={{ marginBottom: '0px', paddingBottom: '10px' }}>
                  <span className="label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'JetBrains Mono' }}>
                    Python 3
                  </span>
                </div>
                <div className="code-editor-container" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                  <CodeMirror
                    value={code}
                    height="100%"
                    theme={vscodeDark}
                    extensions={[python()]}
                    onChange={(val) => setCode(val)}
                    style={{ flex: 1, fontSize: '14px', fontFamily: '"JetBrains Mono", monospace' }}
                  />
                </div>
                {showTestResults && (
                  <div className="test-results" style={{ display: 'block', height: '180px', flexShrink: 0 }}>
                    <h4 style={{ marginBottom: '0.5rem' }}>Test Results</h4>
                    <div id="test-results-list" style={{ display: 'flex', overflowX: 'auto', gap: '1rem', paddingBottom: '0.5rem', width: '100%' }}>
                      {testResults.map((res, i) => (
                        <div key={i} className={`test-case ${res.error ? '' : res.passed ? 'passed' : 'failed'}`} style={{ minWidth: '320px', flex: '0 0 auto' }}>
                          {res.error ? (
                            <p className="error">{res.error}</p>
                          ) : (
                            <>
                              <div className="test-case-header">
                                <span style={{ fontSize: '0.8rem', fontWeight: 500 }}>Case {i + 1}</span>
                                <span className="test-case-status">{res.passed ? 'Passed' : 'Failed'}</span>
                              </div>
                              <div className="test-case-info">
                                <div><strong>Input:</strong> <code>{res.input}</code></div>
                                {res.output && <div><strong>Your Output:</strong> <code>{res.output}</code></div>}
                                {res.expected && <div><strong>Expected:</strong> <code>{res.expected}</code></div>}
                                {res.error && <div className="error"><strong>Error:</strong> {res.error}</div>}
                              </div>
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <div className="panel-footer">
                <button type="button" id="validate-btn" style={{ background: 'rgba(168, 85, 247, 0.1)', color: 'var(--accent)', border: '1px solid rgba(168, 85, 247, 0.2)', borderRadius: 8, padding: '0.5rem 1rem', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem' }}>
                  Ask AI to Validate
                </button>
                <button
                  type="button"
                  id="run-btn"
                  onClick={handleRun}
                  disabled={isLoading}
                  style={{ background: '#27272a', color: 'white', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '0.5rem 1.25rem', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem' }}
                >
                  {isLoading ? 'Running...' : 'Run'}
                </button>
                <button
                  type="button"
                  id="submit-btn"
                  onClick={handleSubmit}
                  disabled={isLoading}
                  style={{ background: 'var(--accent-secondary)', color: '#000', border: 'none', borderRadius: 8, padding: '0.5rem 1.5rem', cursor: 'pointer', fontWeight: 700, fontSize: '0.8rem' }}
                >
                  {isLoading ? 'Submitting...' : 'Submit'}
                </button>
              </div>
            </div>
          </div>

        </div>
      )}

      <div className={`aries-bot ${isAriesTalking ? 'talking' : ''}`}>
        <img src="/logo.png" alt="Aries" />
        <div className="aries-glow"></div>
        {showAriesBubble && (
          <div className={`aries-bubble ${showAriesBubble ? 'show' : ''}`}>
            {ariesBubble}
          </div>
        )}
      </div>

      <div className="toast-container">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast toast-${toast.type}`} onClick={() => removeToast(toast.id)}>
            {toast.message}
          </div>
        ))}
      </div>
    </>
  )
}

export default App
