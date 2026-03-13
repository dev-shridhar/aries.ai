import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useVoiceSocket } from './useVoiceSocket';
import AudioVisualizer from './AudioVisualizer';
import './VoiceAgent.css';

interface VoiceAgentProps {
    currentCode: string;
    onAction?: (action: string, payload: any) => void;
    onSessionInit?: (sessionId: string, username: string) => void;
}
const VoiceAgent: React.FC<VoiceAgentProps> = ({ currentCode, onAction, onSessionInit }) => {
    const [isActive, setIsActive] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isThinking, setIsThinking] = useState(false);
    const [bubbleText, setBubbleText] = useState<string | null>("Summon\nme!!!");
    const [isAudioBlocked, setIsAudioBlocked] = useState(false);

    const isActiveRef = useRef(false);
    useEffect(() => {
        isActiveRef.current = isActive;
    }, [isActive]);

    const onSessionInitRef = useRef(onSessionInit);
    useEffect(() => {
        onSessionInitRef.current = onSessionInit;
    }, [onSessionInit]);

    const handleAudioChunk = useCallback((chunk: string) => {
        audioQueueRef.current.push(chunk);
        if (!isPlayingRef.current) {
            processAudioQueue();
        }
    }, []);

    const { isConnected, lastResponse, partialTranscript, sendVoiceChunk, sendVoiceRequest, sessionId, username, aiResponse, setAiResponse } = useVoiceSocket(
        'ws://localhost:8000/api/aries/ws',
        handleAudioChunk
    );

    const isFirstActivationRef = useRef(true);

    // Session Init & Cleanup
    useEffect(() => {
        if (isConnected) {
            console.log("Aries: WebSocket Connected.");
            if (onSessionInitRef.current) {
                onSessionInitRef.current(sessionId, username);
            }

            // Auto-trigger welcome after 1 second of connection
            if (isFirstActivationRef.current) {
                const timer = setTimeout(() => {
                    console.log("Aries: Auto-triggering welcome message...");
                    sendVoiceRequest({ event: "WELCOME" } as any);
                    isFirstActivationRef.current = false;
                }, 1000);
                return () => clearTimeout(timer);
            }
        }
    }, [isConnected, sendVoiceRequest, sessionId, username]);
    // Removed onSessionInit from dependencies to keep size stable and avoid re-renders

    // Instruction Bubble Cycle
    useEffect(() => {
        if (isSpeaking) {
            setBubbleText(aiResponse || "Aries is\nresponding");
        } else if (isThinking) {
            setBubbleText("Aries is\nthinking");
        } else if (isListening) {
            setBubbleText(partialTranscript || "Aries is\nlistening");
        } else if (!isActive) {
            setBubbleText("Summon\nme!!!");
            setAiResponse("");
        }
    }, [isActive, isListening, isThinking, isSpeaking, partialTranscript, aiResponse]);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const audioQueueRef = useRef<string[]>([]);
    const isPlayingRef = useRef(false);

    // Handle Voice Responses (Actions only now)
    useEffect(() => {
        if (lastResponse) {
            if (lastResponse.action === "SENSORY: WAKE") {
                console.log("WAKE WORD DETECTED: Glow active!");
                setIsThinking(true); 
            } else if (lastResponse.action && onAction) {
                onAction(lastResponse.action, lastResponse.action_payload);
            }
        }
    }, [lastResponse, onAction]);

    const processAudioQueue = () => {
        if (audioQueueRef.current.length === 0) {
            isPlayingRef.current = false;
            setIsSpeaking(false);
            return;
        }

        const base64Audio = audioQueueRef.current.shift();
        if (!base64Audio) {
            isPlayingRef.current = false;
            setIsSpeaking(false);
            return;
        }

        isPlayingRef.current = true;
        setIsSpeaking(true);
        
        const audio = new Audio(`data:audio/mpeg;base64,${base64Audio}`);
        audio.onended = () => {
            processAudioQueue();
        };
        audio.play().catch(err => {
            console.error("Aries UI: Audio playback error:", err);
            if (err.name === 'NotAllowedError') {
                console.warn("Aries UI: Audio blocked by browser. Queuing for first gesture.");
                setIsAudioBlocked(true);
                // Put the chunk back at the start of the queue
                audioQueueRef.current.unshift(base64Audio);
                isPlayingRef.current = false;
                setIsSpeaking(false);
            } else {
                processAudioQueue();
            }
        });
    };

    const startRecording = async () => {
        setAiResponse(""); // Clear previous Aries response
        audioQueueRef.current = []; // Clear stale audio
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            if (!isActiveRef.current) {
                stream.getTracks().forEach(track => track.stop());
                return;
            }

            streamRef.current = stream;
            // Use 250ms slices for real-time streaming
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorderRef.current = mediaRecorder;

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    // console.debug(`Aries: Sending audio blob of size ${event.data.size}`);
                    sendVoiceChunk(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                setIsListening(false);
            };

            mediaRecorder.start(250);
            setIsListening(true);
            
            // Send metadata to backend
            sendVoiceRequest({
                code_context: currentCode,
                skill_id: "aries-default"
            });

        } catch (err) {
            console.error('Error accessing microphone:', err);
            setIsActive(false);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
        }
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
    };

    const toggleVoiceSession = () => {
        if (!isActive) {
            setIsActive(true);
            isActiveRef.current = true;
            
            if (isAudioBlocked) {
                console.log("Aries UI: Resuming blocked audio queue...");
                setIsAudioBlocked(false);
                processAudioQueue();
            }

            // Activation: Start recording
            startRecording();
        } else {
            isActiveRef.current = false;
            stopRecording();
            setIsActive(false);
            setIsSpeaking(false);
            setIsThinking(false);
            audioQueueRef.current = [];
        }
    };

    return (
        <div className={`voice-agent-container ${isActive ? 'active' : ''}`} onClick={toggleVoiceSession}>
            <AudioVisualizer
                isListening={isListening}
                isSpeaking={isSpeaking}
                isThinking={isThinking}
                bubbleText={bubbleText}
            />
        </div>
    );
};

export default VoiceAgent;
