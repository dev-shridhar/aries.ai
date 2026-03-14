import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useVoiceSocket } from './useVoiceSocket';
import AudioVisualizer from './AudioVisualizer';
import './VoiceAgent.css';

interface VoiceAgentProps {
    view: string;
    currentCode: string;
    onAction?: (action: string, payload: any) => void;
    onSessionInit?: (sessionId: string, username: string) => void;
}
const VoiceAgent: React.FC<VoiceAgentProps> = ({ view, currentCode, onAction, onSessionInit }) => {
    const [isActive, setIsActive] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isThinking, setIsThinking] = useState(false);
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
        } else {
            // Reset states if connection is lost
            setIsListening(false);
            setIsThinking(false);
            setIsSpeaking(false);
            audioQueueRef.current = [];
            isPlayingRef.current = false;
        }
    }, [isConnected, sessionId, username]);
    // Removed onSessionInit from dependencies to keep size stable and avoid re-renders

    // Instruction Bubble Cycle (Legacy - removed updates)
    useEffect(() => {
        // No updates to bubble text anymore as per user request
    }, [isActive, isListening, isThinking, isSpeaking, aiResponse]);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const streamRef = useRef<MediaStream | null>(null);
    const audioQueueRef = useRef<string[]>([]);
    const isPlayingRef = useRef(false);
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const silenceTimerRef = useRef<number | null>(null);

    // Handle Voice Responses (Actions only now)
    useEffect(() => {
        if (lastResponse) {
            // If we got ANY response from the backend, we definitely aren't "thinking" about the previous turn anymore
            setIsThinking(false);

            if (lastResponse.action === "SENSORY: WAKE") {
                console.log("WAKE WORD DETECTED: Glow active!");
                setIsThinking(true); 
            } else if (lastResponse.action && onAction) {
                onAction(lastResponse.action, lastResponse.action_payload);
            }
        }
    }, [lastResponse, onAction]);

    const base64ToBlob = (base64: string, type = 'audio/wav') => {
        const binStr = atob(base64);
        const len = binStr.length;
        const arr = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            arr[i] = binStr.charCodeAt(i);
        }
        return new Blob([arr], { type });
    };

    const processAudioQueue = () => {
        const base64Audio = audioQueueRef.current.shift();
        if (!base64Audio) {
            console.log("Aries: Audio queue empty, ending playback flow.");
            isPlayingRef.current = false;
            setIsSpeaking(false);
            // If we are active (not clicked to stop), go back to listening
            if (isActiveRef.current) {
                console.log("Aries: Response complete, starting recording phase...");
                startRecording();
            }
            return;
        }

        console.log("Aries: Starting playback of audio chunk...");
        isPlayingRef.current = true;
        setIsSpeaking(true);
        
        try {
            const blob = base64ToBlob(base64Audio);
            console.log(`Aries: Created blob of size ${blob.size}`);
            const url = URL.createObjectURL(blob);
            const audio = new Audio();
            audio.src = url;
            audio.preload = 'auto';
            audio.volume = 1.0;
            
            audio.onended = () => {
                console.log("Aries: Audio chunk ended.");
                URL.revokeObjectURL(url);
                setIsSpeaking(false);
                processAudioQueue();
            };

            audio.onerror = (e) => {
                console.error("Aries UI: Audio element error:", e);
                URL.revokeObjectURL(url);
                processAudioQueue();
            };

            audio.play().then(() => {
                console.log("Aries: Audio playback started successfully.");
            }).catch(err => {
                console.error("Aries UI: Audio playback error:", err);
                URL.revokeObjectURL(url);
                if (err.name === 'NotAllowedError' || err.name === 'AbortError') {
                    console.warn("Aries: Audio blocked or aborted.");
                    setIsAudioBlocked(true);
                    audioQueueRef.current.unshift(base64Audio);
                    isPlayingRef.current = false;
                    setIsSpeaking(false);
                } else {
                    processAudioQueue();
                }
            });
        } catch (err) {
            console.error("Aries UI: Error preparing audio:", err);
            processAudioQueue();
        }
    };

    const startRecording = async () => {
        console.log("Aries: Entering startRecording...");
        setAiResponse(""); // Clear previous Aries response
        audioQueueRef.current = []; // Clear stale audio
        setIsListening(true); // Show Cyan immediately
        setIsThinking(false);
        try {
            console.log("Aries: Requesting microphone access...");
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log("Aries: Microphone access granted.");
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
                    console.log(`Aries: Sending audio blob (${event.data.size} bytes)`);
                    sendVoiceChunk(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                setIsListening(false);
                // Only show thinking if we are still active (not clicked to stop)
                if (isActiveRef.current) {
                    setIsThinking(true);
                    // Explicitly tell backend to process the accumulated buffer
                    sendVoiceRequest({ event: "PROCESS_AUDIO" } as any);
                }
            };

            mediaRecorder.start(1000); // Send data every second as a fallback, but mostly for the final blob
            setIsListening(true);
            setIsThinking(false); // Stop thinking once we start listening
            
            // --- SIMPLE VAD LOGIC ---
            const audioContext = new AudioContext();
            audioContextRef.current = audioContext;
            const source = audioContext.createMediaStreamSource(stream);
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            source.connect(analyser);
            analyserRef.current = analyser;

            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            let silenceStart = Date.now();
            let hasSpoken = false; // Prevent immediate timeout before speech starts
            const SILENCE_THRESHOLD = 0.015; // Slightly more robust threshold
            const SILENCE_DURATION = 800; // 0.8 seconds

            console.log("Aries: VAD loop starting...");
            
            // Handle browser Autoplay policy
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }

            const VAD_WARMUP = 1000; // Wait 1s before allowing silence detection
            const startTime = Date.now();

            const checkVolume = () => {
                if (!isActiveRef.current || mediaRecorder.state !== 'recording') {
                    return;
                }
                
                analyser.getByteTimeDomainData(dataArray);
                
                let sumSquares = 0;
                for (let i = 0; i < bufferLength; i++) {
                    const normalized = (dataArray[i] - 128) / 128;
                    sumSquares += normalized * normalized;
                }
                const rms = Math.sqrt(sumSquares / bufferLength);

                const isWarmedUp = Date.now() - startTime > VAD_WARMUP;

                if (rms > SILENCE_THRESHOLD) {
                    silenceStart = Date.now();
                    if (!hasSpoken) {
                        console.log("Aries VAD: Speech detected, silence monitoring engaged.");
                        hasSpoken = true;
                    }
                } else if (hasSpoken && isWarmedUp && Date.now() - silenceStart > SILENCE_DURATION) {
                    console.log(`Aries: VAD detected silence (${rms.toFixed(4)}), stopping turn...`);
                    stopRecording();
                    return; 
                }
                
                requestAnimationFrame(checkVolume);
            };
            requestAnimationFrame(checkVolume);
            // ------------------------

            // Send metadata to backend
            sendVoiceRequest({
                code_context: currentCode,
                skill_id: "aries-default"
            });

        } catch (err) {
            console.error('Error accessing microphone:', err);
            setIsActive(false);
            isActiveRef.current = false;
        }
    };

    const stopRecording = () => {
        console.log("Aries: stopRecording called");
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.requestData(); // Force emission of buffered audio
            mediaRecorderRef.current.stop();
        }
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
    };

    const toggleVoiceSession = () => {
        if (!isActive) {
            setIsActive(true);
            isActiveRef.current = true;
            
            console.log("Aries: Triggering backend WELCOME.");
            setIsThinking(true);
            sendVoiceRequest({ event: "WELCOME" } as any);
            
            if (isAudioBlocked) {
                setIsAudioBlocked(false);
            }
        } else {
            console.log("Aries: User clicked to STOP session.");
            isActiveRef.current = false;
            stopRecording();
            setIsActive(false);
            setIsSpeaking(false);
            setIsThinking(false);
            setIsListening(false);
            audioQueueRef.current = [];
            setAiResponse("");
        }
    };

    return (
        <div className={`voice-agent-container ${isActive ? 'active' : ''}`} onClick={toggleVoiceSession}>
            <AudioVisualizer
                isListening={isListening}
                isSpeaking={isSpeaking}
                isThinking={isThinking}
            />
        </div>
    );
};

export default VoiceAgent;
