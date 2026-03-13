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
  
  const onAudioChunkRef = useRef(onAudioChunk);
  useEffect(() => {
    onAudioChunkRef.current = onAudioChunk;
  }, [onAudioChunk]);

  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const usernameRef = useRef<string>(localStorage.getItem('aries_username') || 'anonymous');

  const connect = useCallback(() => {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('Voice WebSocket connected');
      setIsConnected(true);
      
      // Initialize session state on backend
      ws.send(JSON.stringify({
          session_id: sessionIdRef.current,
          username: usernameRef.current
      }));
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
      setIsConnected(false);
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error('Voice WebSocket error', err);
    };

    setSocket(ws);
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      if (socket) socket.close();
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    };
  }, [connect]);

  const sendVoiceRequest = useCallback((request: VoiceRequest) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        ...request,
        session_id: sessionIdRef.current,
        username: usernameRef.current
      }));
    }
  }, [socket]);

  const sendVoiceChunk = useCallback((chunk: Blob | ArrayBuffer) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(chunk);
    }
  }, [socket]);

  return {
    isConnected,
    lastResponse,
    partialTranscript,
    sendVoiceRequest,
    sendVoiceChunk,
    setAiResponse,
    aiResponse,
    sessionId: sessionIdRef.current,
    username: usernameRef.current
  };
};
