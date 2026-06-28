import { useState, useEffect, useRef, useCallback } from 'react'

function VoiceAgent({ currentCode }) {
  const [active, setActive] = useState(false)
  const [listening, setListening] = useState(false)
  const [thinking, setThinking] = useState(false)
  const [speaking, setSpeaking] = useState(false)

  const activeRef = useRef(false)
  const wsRef = useRef(null)
  const recRef = useRef(null)
  const streamRef = useRef(null)
  const audioRef = useRef(null)
  const bufRef = useRef([])
  const playingRef = useRef(false)
  const sidRef = useRef(crypto.randomUUID())

  useEffect(() => { activeRef.current = active }, [active])

  useEffect(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}/ws`)
    ws.onopen = () => {
      ws.send(JSON.stringify({ session_id: sidRef.current }))
    }
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.audio) {
        bufRef.current.push(msg.audio)
        if (!playingRef.current) playNext()
      }
      if (msg.text) {
        setThinking(false)
      }
    }
    ws.onclose = () => setTimeout(() => { /* reconnect */ }, 3000)
    wsRef.current = ws
    return () => ws.close()
  }, [])

  const playNext = () => {
    const b64 = bufRef.current.shift()
    if (!b64) { playingRef.current = false; setSpeaking(false); if (activeRef.current) startRec(); return }
    playingRef.current = true
    setSpeaking(true)
    const blob = new Blob([Uint8Array.from(atob(b64), c => c.charCodeAt(0))], { type: 'audio/wav' })
    const url = URL.createObjectURL(blob)
    const a = new Audio(url)
    a.onended = () => { URL.revokeObjectURL(url); playNext() }
    a.play().catch(() => { playingRef.current = false; setSpeaking(false) })
    audioRef.current = a
  }

  const startRec = async () => {
    setListening(true)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!activeRef.current) { stream.getTracks().forEach(t => t.stop()); return }
      streamRef.current = stream
      const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      recRef.current = rec
      rec.ondataavailable = (e) => { if (e.data.size > 0) wsRef.current?.send(e.data) }
      rec.onstop = () => {
        setListening(false)
        if (activeRef.current) { setThinking(true); wsRef.current?.send(JSON.stringify({ event: 'PROCESS_AUDIO', code_context: currentCode })) }
      }
      rec.start(1000)
    } catch {
      setActive(false); activeRef.current = false
    }
  }

  const stopRec = () => {
    if (recRef.current && recRef.current.state !== 'inactive') { recRef.current.requestData(); recRef.current.stop() }
    streamRef.current?.getTracks().forEach(t => t.stop())
    audioRef.current?.pause()
  }

  const toggle = () => {
    if (!active) { setActive(true); activeRef.current = true; setThinking(true); wsRef.current?.send(JSON.stringify({ event: 'WELCOME' })) }
    else { activeRef.current = false; stopRec(); setActive(false); setSpeaking(false); setThinking(false); setListening(false); bufRef.current = [] }
  }

  return (
    <div className="vc" onClick={toggle}>
      <div className={`vc-mascot ${listening ? 'listening' : thinking ? 'thinking' : speaking ? 'speaking' : ''}`}>
        {listening ? '🎤' : thinking ? '🧠' : speaking ? '🔊' : '🦊'}
      </div>
    </div>
  )
}

export default VoiceAgent
