import { useState, useCallback, useMemo } from 'react';
import { RACING_PHYSICS_KNOWLEDGE } from '../utils/coachingKnowledge';
import { convertToWav } from '../utils/audioUtils';
import { GoogleGenAI, Modality } from '@google/genai';
import { GeminiService } from '../services/geminiService';
import type { CloudModel } from '../types';

interface CloudStatus {
  state: 'idle' | 'loading' | 'error' | 'success';
  error?: string;
  hasKey: boolean;
}

export const useGeminiCloud = () => {
  const [apiKey, setAutoApiKey] = useState<string | null>(() =>
    localStorage.getItem('gemini_api_key') || null
  );

  const [status, setStatus] = useState<CloudStatus>({
    state: 'idle',
    hasKey: !!apiKey,
  });

  const geminiService = useMemo(() => new GeminiService(), []);

  const setApiKey = useCallback((key: string) => {
    if (key) {
      localStorage.setItem('gemini_api_key', key);
      setAutoApiKey(key);
      setStatus(prev => ({ ...prev, hasKey: true }));
    } else {
      localStorage.removeItem('gemini_api_key');
      setAutoApiKey(null);
      setStatus(prev => ({ ...prev, hasKey: false }));
    }
  }, []);

  const generateFeedback = useCallback(
    async (model: CloudModel, contextString: string) => {
      setStatus(prev => ({ ...prev, state: 'loading', error: undefined }));

      try {
        let text = '';
        if (model === 'pro') {
          text = await geminiService.analyzeLap(contextString);
        } else {
          text = await geminiService.generateCoaching(contextString);
        }

        setStatus(prev => ({ ...prev, state: 'success' }));
        return text;
      } catch (err: unknown) {
        console.error('Gemini Cloud failed:', err);
        setStatus(prev => ({ ...prev, state: 'error', error: (err as Error).message }));
        return '';
      }
    },
    [geminiService]
  );

  const generateAudio = useCallback(async (text: string, voiceName = 'Zephyr'): Promise<Blob | null> => {
    if (!apiKey) return null;
    try {
      const client = new GoogleGenAI({ apiKey, httpOptions: { apiVersion: 'v1alpha' } });

      const response = await client.models.generateContentStream({
        model: 'models/gemini-2.5-pro-preview-tts',
        config: {
          responseModalities: [Modality.AUDIO],
          speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName } } },
        },
        contents: [{ role: 'user', parts: [{ text: `Read aloud verbatim: "${text}"` }] }],
      });

      const audioParts: string[] = [];
      let audioMimeType = '';

      for await (const chunk of response) {
        const inlineData = chunk.candidates?.[0]?.content?.parts?.[0]?.inlineData;
        if (inlineData) {
          audioParts.push(inlineData.data || '');
          if (!audioMimeType && inlineData.mimeType) audioMimeType = inlineData.mimeType;
        }
      }

      if (audioParts.length > 0) {
        const wavBuffer = convertToWav(audioParts, audioMimeType || 'audio/pcm; rate=24000');
        return new Blob([wavBuffer], { type: 'audio/wav' });
      }
      return null;
    } catch (e) {
      console.error('Audio gen failed:', e);
      return null;
    }
  }, [apiKey]);

  return { status, generateFeedback, generateAudio, setApiKey, apiKey };
};
