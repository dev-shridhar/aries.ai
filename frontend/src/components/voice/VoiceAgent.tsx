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
        // When we receive audio, we're now speaking (not thinking)
        setIsThinking(false);
        setIsListening(false);
        
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
        }
    }, [isConnected, sessionId, username]);
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
    const shouldStartRecordingRef = useRef(false);

    // Handle Voice Responses
    useEffect(() => {
        if (lastResponse) {
            // When we get audio response, stop recording and play audio
            if (lastResponse.audio_chunk) {
                console.log("Aries UI: Received audio response, stopping recording");
                stopRecording();
                setIsThinking(false);
                setIsListening(false);
            }
            
            if (lastResponse.action === "SENSORY: WAKE") {
                console.log("WAKE WORD DETECTED: Glow active!");
                setIsThinking(true); 
            } else if (lastResponse.action === "SENSORY: PROCESSING") {
                console.log("PROCESSING: Aries is thinking");
                setIsListening(false);
                setIsThinking(true);
                setIsSpeaking(false);
            } else if (lastResponse.action && onAction) {
                onAction(lastResponse.action, lastResponse.action_payload);
            }
            
            // When audio chunk arrives, we're speaking (not thinking anymore)
            if (lastResponse.audio_chunk) {
                setIsThinking(false);
                setIsListening(false);
            }
        }
    }, [lastResponse, onAction]);

    const processAudioQueue = () => {
        if (audioQueueRef.current.length === 0) {
            isPlayingRef.current = false;
            setIsSpeaking(false);
            
            // If welcome audio completed, start recording
            if (shouldStartRecordingRef.current) {
                shouldStartRecordingRef.current = false;
                console.log("Aries UI: Welcome audio done, starting recording");
                startRecording();
            }
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
            // Check if we should start recording after audio
            if (shouldStartRecordingRef.current) {
                console.log("Aries UI: Audio done, starting recording");
                shouldStartRecordingRef.current = false;
                startRecording();
            } else {
                processAudioQueue();
            }
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
        setIsThinking(false);  // Stop thinking
        setIsSpeaking(false);   // Not speaking yet
        setIsListening(true);   // Now listening
        
        try {
            console.log("Aries UI: Requesting microphone access...");
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true
                } 
            });
            console.log("Aries UI: Microphone access granted, tracks:", stream.getTracks().length);
            
            if (!isActiveRef.current) {
                stream.getTracks().forEach(track => track.stop());
                return;
            }

            streamRef.current = stream;
            
            // Use MediaRecorder to capture complete audio
            const audioChunks: Blob[] = [];
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorderRef.current = mediaRecorder;

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                console.log("Aries UI: Recording stopped, processing audio");
                setIsListening(false);
                
                // Combine all chunks into single blob
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                
                // Convert to base64 and send
                const reader = new FileReader();
                reader.onloadend = () => {
                    const base64 = (reader.result as string).split(',')[1];
                    sendVoiceRequest({ audio_chunk: base64 });
                };
                reader.readAsDataURL(audioBlob);
            };

            mediaRecorder.onerror = (event: any) => {
                console.error("Aries UI: MediaRecorder error:", event);
            };

            mediaRecorder.start(1000);  // Collect in 1sec chunks
            setIsListening(true);
            console.log("Aries UI: Recording started");
            
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
            
            // Play any queued welcome audio first
            if (audioQueueRef.current.length > 0) {
                console.log("Aries UI: Playing queued audio first...");
                setIsAudioBlocked(false);
                setIsThinking(true);
                processAudioQueue();
            } else {
                // No queued audio - start recording immediately
                console.log("Aries UI: Starting recording immediately");
                setIsThinking(false);
                startRecording();
            }
        } else {
            // Deactivate
            isActiveRef.current = false;
            stopRecording();
            setIsActive(false);
            setIsSpeaking(false);
            setIsThinking(false);
            setIsListening(false);
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
