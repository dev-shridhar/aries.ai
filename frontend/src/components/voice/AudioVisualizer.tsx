import React from 'react';
import './AudioVisualizer.css';

interface AudioVisualizerProps {
    isListening: boolean;
    isSpeaking: boolean;
    isThinking: boolean;
    bubbleText?: string | null;
}

const AudioVisualizer: React.FC<AudioVisualizerProps> = ({ isListening, isSpeaking, isThinking, bubbleText }) => {
    return (
        <div className={`aries-visualizer-container ${isListening ? 'listening' : ''} ${isSpeaking ? 'speaking' : ''} ${isThinking ? 'thinking' : ''}`}>
            <div className="aries-core">
                <div className="aries-mascot">
                    {bubbleText && (
                        <div className="aries-mascot-bubble">
                            {bubbleText}
                        </div>
                    )}
                    <img src="/logo.png" alt="Aries Mascot" className="aries-mascot-img" />
                </div>
            </div>
        </div>
    );
};

export default AudioVisualizer;
