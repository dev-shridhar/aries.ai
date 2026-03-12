import React, { useState, useEffect, useRef } from 'react';
import { useVoiceSocket } from './useVoiceSocket';
import AudioVisualizer from './AudioVisualizer';
import './VoiceAgent.css';

interface VoiceAgentProps {
    currentCode: string;
    onAction?: (action: string, payload: any) => void;
}

const VoiceAgent: React.FC<VoiceAgentProps> = ({ currentCode, onAction }) => {
    const [isActive, setIsActive] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isThinking, setIsThinking] = useState(false);
    const [bubbleText, setBubbleText] = useState<string | null>("Summon\nme!!!");

    const isActiveRef = useRef(false);
    useEffect(() => {
        isActiveRef.current = isActive;
    }, [isActive]);

    const { isConnected, lastResponse, sendVoiceRequest } = useVoiceSocket('ws://localhost:8000/api/aries/ws');

    // Instruction Bubble Cycle
    useEffect(() => {
        if (!isActive) {
            setBubbleText("Summon\nme!!!");
        } else if (isListening) {
            setBubbleText("Listening");
        } else if (isThinking) {
            setBubbleText("Thinking");
        } else if (isSpeaking) {
            setBubbleText("Responding");
        }
    }, [isActive, isListening, isThinking, isSpeaking]);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const streamRef = useRef<MediaStream | null>(null);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(track => track.stop());
            }
        };
    }, []);

    // Handle Voice Responses
    useEffect(() => {
        if (lastResponse) {
            setIsThinking(false);

            if (lastResponse.audio_chunk) {
                playAudio(lastResponse.audio_chunk);
            }

            if (lastResponse.action && onAction) {
                onAction(lastResponse.action, lastResponse.action_payload);
            }
        }
    }, [lastResponse, onAction]);

    const playAudio = (base64Audio: string) => {
        setIsSpeaking(true);
        const audio = new Audio(`data:audio/mpeg;base64,${base64Audio}`);
        audio.onended = () => {
            setIsSpeaking(false);
            // Resume listening ONLY if the session is STILL active
            if (isActiveRef.current) startRecording();
        };
        audio.play();
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Critical Race Condition Check: 
            // If the user stopped the session while we were waiting for the mic, 
            // kill the stream immediately and don't start recording.
            if (!isActiveRef.current && stream) {
                stream.getTracks().forEach(track => track.stop());
                return;
            }

            streamRef.current = stream;
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/mpeg' });
                const reader = new FileReader();
                reader.onloadend = () => {
                    if (!isActiveRef.current) return; // Don't send if session ended
                    const base64Audio = (reader.result as string).split(',')[1];
                    sendVoiceRequest({
                        audio_chunk: base64Audio,
                        code_context: currentCode,
                        skill_id: "aries-default"
                    });
                    setIsThinking(true);
                };
                reader.readAsDataURL(audioBlob);
            };

            mediaRecorder.start();
            setIsListening(true);
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
        setIsListening(false);
    };

    const toggleVoiceSession = () => {
        if (isActive) {
            stopRecording();
            setIsActive(false);
        } else {
            setIsActive(true);
            startRecording();
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
