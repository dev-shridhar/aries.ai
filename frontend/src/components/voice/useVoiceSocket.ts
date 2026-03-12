import { useState, useEffect, useCallback, useRef } from 'react';

interface VoiceResponse {
  text: string;
  audio_chunk?: string;
  action?: string;
  action_payload?: any;
}

interface VoiceRequest {
  audio_chunk?: string;
  code_context?: string;
  skill_id?: string;
  session_id?: string;
  username?: string;
}

export const useVoiceSocket = (url: string) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastResponse, setLastResponse] = useState<VoiceResponse | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const usernameRef = useRef<string>(localStorage.getItem('aries_username') || 'anonymous');

  const connect = useCallback(() => {
    const ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('Voice WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const response: VoiceResponse = JSON.parse(event.data);
        setLastResponse(response);
      } catch (err) {
        console.error('Failed to parse voice response', err);
      }
    };

    ws.onclose = () => {
      console.log('Voice WebSocket disconnected');
      setIsConnected(false);
      // Attempt reconnect after 3 seconds
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
      const payload = {
        ...request,
        session_id: sessionIdRef.current,
        username: usernameRef.current
      };
      socket.send(JSON.stringify(payload));
    } else {
      console.warn('Voice WebSocket is not open. ReadyState:', socket?.readyState);
    }
  }, [socket]);

  return { isConnected, lastResponse, sendVoiceRequest };
};
