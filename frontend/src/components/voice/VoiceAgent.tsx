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
    const isConnectedRef = useRef(false);
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
        console.log("Aries: Received audio chunk, length:", chunk.length);
        audioQueueRef.current.push(chunk);
        if (!isPlayingRef.current) {
            console.log("Aries: Not currently playing, starting queue processing");
            processAudioQueue();
        } else {
            console.log("Aries: Already playing, chunk queued");
        }
    }, []);

    const onActionRef = useRef(onAction);
    useEffect(() => {
        onActionRef.current = onAction;
    }, [onAction]);

    const { isConnected, lastResponse, partialTranscript, sendVoiceChunk, sendVoiceRequest, sessionId, username, aiResponse, setAiResponse, socket, socketRef, connect } = useVoiceSocket(
        'ws://localhost:8000/api/aries/ws',
        handleAudioChunk
    );

    // Initial session sync with parent
    useEffect(() => {
        isConnectedRef.current = isConnected;
        if (isConnected && onSessionInitRef.current) {
            onSessionInitRef.current(sessionId, username);
        }
    }, [isConnected, sessionId, username]);

    const isFirstActivationRef = useRef(true);

    // Session Init & Cleanup
    useEffect(() => {
        if (!isConnected) {
            // Reset states if connection is lost
            setIsListening(false);
            setIsThinking(false);
            setIsSpeaking(false);
            audioQueueRef.current = [];
            isPlayingRef.current = false;
        }
    }, [isConnected]);

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

    // Handle Voice Responses
    useEffect(() => {
        if (lastResponse && isActiveRef.current) {
            setIsThinking(false);

            // If this was a response to speech, start listening after audio plays
            // We check !== undefined because "" (empty string) is a valid noise/silence signal from backend
            if ((lastResponse.text !== undefined || lastResponse.audio_chunk) && !lastResponse.action) {
                console.log("Aries: Response received (text length:", lastResponse.text?.length || 0, "), cycling turn...");
                
                // If there's an actual message, the audio play loop or TTS timeout will cycle back.
                // If it's empty (noise/silence), don't auto-restart as it can cause an infinite loop in noisy rooms.
                if (lastResponse.text === "" && !lastResponse.audio_chunk) {
                    console.log("Aries: Noise/silence response, turn ended. (No auto-restaring to avoid loops)");
                    setIsActive(false); // Force stop to be safe
                    setIsThinking(false);
                    return;
                }

                // SAFETY TIMEOUT: If text arrived but no audio starts playing within 2s,
                // it means TTS likely failed or was skipped.
                if (lastResponse.text && !lastResponse.audio_chunk) {
                    setTimeout(() => {
                        if (isActiveRef.current && !isPlayingRef.current && !isListening && !isThinking) {
                            console.warn("Aries: Audio timed out, restoring mic loop.");
                            startRecording();
                        }
                    }, 2500);
                }
                return;
            }

            if (lastResponse.action === "SENSORY: WAKE") {
                console.log("WAKE WORD DETECTED: Glow active!");
                setIsThinking(true); 
            } else if (lastResponse.action && onActionRef.current) {
                onActionRef.current(lastResponse.action, lastResponse.action_payload);
            }
        }
    }, [lastResponse]);

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
        console.log("Aries: processAudioQueue called, audio in queue:", base64Audio ? "yes" : "no");
        if (!base64Audio) {
            console.log("Aries: Audio queue empty, ending playback flow.");
            console.log("Aries: isActiveRef.current =", isActiveRef.current);
            isPlayingRef.current = false;
            setIsSpeaking(false);
            // If we are active (not clicked to stop), wait a moment then go back to listening
            if (isActiveRef.current) {
                console.log("Aries: Response complete, waiting before recording...");
                // Wait 1.5 seconds before listening again to avoid echo/confusion
                setTimeout(() => {
                    if (isActiveRef.current) {
                        console.log("Aries: Starting recording phase after delay...");
                        startRecording();
                    }
                }, 1500);
            } else {
                console.log("Aries: Not starting recording - session was stopped");
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

    const isRecordingInProgressRef = useRef(false);

    const startRecording = async () => {
        // Prevent multiple concurrent recordings
        if (isRecordingInProgressRef.current) {
            console.log("Aries: Recording already in progress, skipping start...");
            return;
        }
        
        console.log("Aries: Entering startRecording...");
        isRecordingInProgressRef.current = true;
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
                const currentReadyState = socketRef.current?.readyState ?? 'unknown';
                console.log("Aries: MediaRecorder onstop triggered. Socket state:", currentReadyState);
                setIsListening(false);
                // Only show thinking if we are still active (not clicked to stop)
                if (isActiveRef.current) {
                    setIsThinking(true);
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
            let hasSpoken = false; 
            const SILENCE_THRESHOLD = 0.05; // Slightly higher to ignore room noise spikes
            const SILENCE_DURATION = 2000; // 2 seconds for breathing room

            console.log("Aries: VAD loop starting...");
            
            // Handle browser Autoplay policy
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }

            const VAD_WARMUP = 500; // Wait 0.5s before allowing silence detection
            
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
                const silenceDuration = Date.now() - silenceStart;

                console.log(`VAD: rms=${rms.toFixed(4)}, hasSpoken=${hasSpoken}, isWarmedUp=${isWarmedUp}, silenceDuration=${silenceDuration}ms`);

                // NO-SPEECH TIMEOUT: Stop if user hasn't spoken for 10 seconds
                if (!hasSpoken && Date.now() - startTime > 10000) {
                    console.log("Aries: No speech detected for 10s, stopping...");
                    stopRecording();
                    return;
                }

                if (rms > SILENCE_THRESHOLD) {
                    silenceStart = Date.now();
                    if (!hasSpoken) {
                        console.log("Aries VAD: Speech detected, silence monitoring engaged.");
                        hasSpoken = true;
                    }
                } else if (hasSpoken && isWarmedUp && silenceDuration > SILENCE_DURATION) {
                    console.log(`Aries: VAD detected silence (rms=${rms.toFixed(4)}, duration=${silenceDuration}ms), stopping turn...`);
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
            isRecordingInProgressRef.current = false;
        }
    };

    const stopRecording = () => {
        console.log("Aries: stopRecording called");
        
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
        }
        
        // Send PROCESS_AUDIO event
        console.log("Aries: Requesting PROCESS_AUDIO...");
        sendVoiceRequest({ event: "PROCESS_AUDIO" });
        
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
        if (audioContextRef.current) {
            audioContextRef.current.close();
            audioContextRef.current = null;
        }
        
        // Allow new recordings
        isRecordingInProgressRef.current = false;
    };

    const toggleVoiceSession = () => {
        if (!isActive) {
            setIsActive(true);
            isActiveRef.current = true;
            
            // Initiate connection on click
            connect();
            
            // startRecording(); // REMOVED: Should only start after Aries speaks
            setIsThinking(true);
            sendVoiceRequest({ event: "WELCOME" });
            
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
