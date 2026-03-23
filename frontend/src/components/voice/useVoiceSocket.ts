import { useState, useEffect, useCallback, useRef } from 'react';

interface VoiceResponse {
  text: string;
  audio_chunk?: string;
  action?: string;
  action_payload?: any;
  is_final?: boolean;
  speech_final?: boolean;
}

interface VoiceRequest {
  event?: string;
  audio_chunk?: string;
  code_context?: string;
  skill_id?: string;
  session_id?: string;
  username?: string;
}

export const useVoiceSocket = (url: string, onAudioChunk?: (chunk: string) => void) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastResponse, setLastResponse] = useState<VoiceResponse | null>(null);
  const [partialTranscript, setPartialTranscript] = useState<string>('');
  const [aiResponse, setAiResponse] = useState<string>('');
  
  // Use ref for socket to avoid stale closures
  const socketRef = useRef<WebSocket | null>(null);
  
  const onAudioChunkRef = useRef(onAudioChunk);
  useEffect(() => {
    onAudioChunkRef.current = onAudioChunk;
  }, [onAudioChunk]);

  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const getSessionId = () => {
    const saved = localStorage.getItem('aries_session_id');
    if (saved) return saved;
    const newId = crypto.randomUUID();
    localStorage.setItem('aries_session_id', newId);
    return newId;
  };
  const sessionIdRef = useRef<string>(getSessionId());
  const usernameRef = useRef<string>(localStorage.getItem('aries_username') || 'anonymous');
  const messageQueueRef = useRef<string[]>([]);

  const wasIntentionallyClosedRef = useRef(false);
  const isConnectingRef = useRef(false);

  const connect = useCallback(() => {
    if (socketRef.current && (socketRef.current.readyState === WebSocket.OPEN || socketRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = undefined;
    }

    isConnectingRef.current = true;
    wasIntentionallyClosedRef.current = false;

    const ws = new WebSocket(url);
    socketRef.current = ws;

    ws.onopen = () => {
      console.log('Voice WebSocket connected');
      isConnectingRef.current = false;
      setIsConnected(true);
      
      // Initialize session state on backend
      ws.send(JSON.stringify({
          session_id: sessionIdRef.current,
          username: usernameRef.current
      }));

      // Flush queued messages
      while (messageQueueRef.current.length > 0) {
        const msg = messageQueueRef.current.shift();
        if (msg) ws.send(msg);
      }
    };

    ws.onmessage = (event) => {
      try {
        const response: VoiceResponse = JSON.parse(event.data);
        
        if (response.is_final != null) {
          // It's a transcript update (STT)
          setPartialTranscript(response.text);
          if (response.speech_final) {
              setPartialTranscript(''); // Clear on end of speech
          }
        } else {
          // It's a brain response (text, audio, or action)
          if (response.text) {
              setAiResponse(prev => (prev + " " + response.text).trim());
          }
          if (response.audio_chunk && onAudioChunkRef.current) {
              onAudioChunkRef.current(response.audio_chunk);
          }
          setLastResponse(response);
          
          // Clear aiResponse when a new user turn starts? 
          // No, we'll let VoiceAgent handle clearing.
        }
      } catch (err) {
        console.error('Failed to parse voice response', err);
      }
    };

    ws.onclose = () => {
      console.log('Voice WebSocket disconnected');
      isConnectingRef.current = false;
      setIsConnected(false);
      
      if (!wasIntentionallyClosedRef.current) {
          console.log('Scheduling reconnect in 3 seconds...');
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
          }
          reconnectTimeoutRef.current = setTimeout(connect, 3000);
      }
    };

    ws.onerror = (err) => {
      isConnectingRef.current = false;
      // Only log as error if it's a "real" failure, not a cleanup close
      if (!wasIntentionallyClosedRef.current) {
          console.error('Voice WebSocket error', err);
      }
    };

    setSocket(ws);
  }, [url]);

  useEffect(() => {
    // connect(); // Removed auto-connect on load
    return () => {
      if (socketRef.current) {
        wasIntentionallyClosedRef.current = true;
        if (socketRef.current.readyState !== WebSocket.CLOSED && socketRef.current.readyState !== WebSocket.CLOSING) {
            socketRef.current.close();
        }
      }
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  const sendVoiceRequest = useCallback((request: VoiceRequest) => {
    const msg = JSON.stringify({
      ...request,
      session_id: sessionIdRef.current,
      username: usernameRef.current
    });

    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      console.log('useVoiceSocket: [SENDING] ', request.event || 'METADATA');
      socketRef.current.send(msg);
    } else {
      console.warn('useVoiceSocket: [QUEUING] ', request.event || 'METADATA', 'state:', socketRef.current?.readyState);
      messageQueueRef.current.push(msg);
    }
  }, []);

  const sendVoiceChunk = useCallback((chunk: Blob | ArrayBuffer) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      console.log('Sending voice chunk, socket state:', socketRef.current.readyState, 'chunk size:', chunk instanceof Blob ? chunk.size : 'arraybuffer');
      socketRef.current.send(chunk);
    } else {
      console.warn('Cannot send voice chunk - socket not open, state:', socketRef.current?.readyState);
    }
  }, []);

  return {
    isConnected,
    lastResponse,
    partialTranscript,
    sendVoiceRequest,
    sendVoiceChunk,
    setAiResponse,
    aiResponse,
    socket,
    socketRef,
    sessionId: sessionIdRef.current,
    username: usernameRef.current,
    connect
  };
};
