import { useState, useCallback, useRef, useMemo } from 'react';
import { GeminiService } from '../services/geminiService';
import type { TTSProvider } from '../types';

// Gemini prebuilt voice per persona
const PERSONA_GEMINI_VOICE: Record<string, string> = {
  aj:      'Fenrir',   // assertive, clipped male
  rachel:  'Kore',     // calm, precise female
  tony:    'Puck',     // upbeat, energetic
  garmin:  'Charon',   // neutral, flat
  superaj: 'Zephyr',   // balanced, adaptive
};

// Browser TTS tuning per persona
const PERSONA_BROWSER_CONFIG: Record<string, { rate: number; pitch: number }> = {
  aj:      { rate: 1.3, pitch: 0.7 },  // fast, low — blunt commands
  rachel:  { rate: 1.0, pitch: 1.1 },  // measured, slightly higher — clinical
  tony:    { rate: 1.4, pitch: 1.3 },  // fast, high — hype energy
  garmin:  { rate: 0.9, pitch: 0.6 },  // slow, flat — robotic data readout
  superaj: { rate: 1.1, pitch: 0.9 },  // default
};

interface TTSState {
  provider: TTSProvider;
  isSpeaking: boolean;
}

export const useTTS = (coachId: string = 'superaj') => {
  const [state, setState] = useState<TTSState>({ provider: 'browser', isSpeaking: false });
  const isFetchingRef = useRef(false);
  const geminiService = useMemo(() => new GeminiService(), []);

  const setProvider = useCallback((provider: TTSProvider) => {
    setState(prev => ({ ...prev, provider }));
  }, []);

  const speak = useCallback(async (text: string) => {
    if (!text.trim() || isFetchingRef.current) return;

    setState(prev => ({ ...prev, isSpeaking: true }));
    isFetchingRef.current = true;

    const voice = PERSONA_GEMINI_VOICE[coachId] ?? 'Zephyr';
    const browserConfig = PERSONA_BROWSER_CONFIG[coachId] ?? { rate: 1.1, pitch: 0.9 };

    try {
      if (state.provider === 'gemini') {
        await speakGemini(text, geminiService, voice);
      } else {
        await speakBrowser(text, browserConfig);
      }
    } catch (err) {
      console.error('TTS error, falling back to browser:', err);
      await speakBrowser(text, browserConfig);
    } finally {
      isFetchingRef.current = false;
      setState(prev => ({ ...prev, isSpeaking: false }));
    }
  }, [state.provider, coachId, geminiService]);

  return { ...state, setProvider, speak };
};

// ── Provider implementations ────────────────────────────────

function speakBrowser(text: string, config: { rate: number; pitch: number }): Promise<void> {
  return new Promise(resolve => {
    if (!('speechSynthesis' in window)) { resolve(); return; }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = config.rate;
    utterance.pitch = config.pitch;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    speechSynthesis.speak(utterance);
  });
}

async function speakGemini(text: string, geminiService: GeminiService, voice: string): Promise<void> {
  const blob = await geminiService.generateAudio(text, voice);
  if (blob) {
    await playBlobAudio(blob);
  } else {
    throw new Error('Failed to generate audio via backend');
  }
}

// ── Playback helpers ────────────────────────────────────────

function playBlobAudio(blob: Blob): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
    audio.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Playback failed')); };
    audio.play();
  });
}
