import { useState, useEffect } from 'react'

function App() {
  const [view, setView] = useState('home')

  return (
    <div id="app">
      {view === 'home' && (
        <div>
          <h1>aries.ai</h1>
          <p>voice dsa tutor</p>
        </div>
      )}
    </div>
  )
}

export default App
