import { useState, useCallback, useMemo } from 'react';
import { GeminiService } from '../services/geminiService';
import type { CloudModel } from '../types';

interface CloudStatus {
  state: 'idle' | 'loading' | 'error' | 'success';
  error?: string;
}

export const useGeminiCloud = () => {
  const [status, setStatus] = useState<CloudStatus>({
    state: 'idle',
  });

  const geminiService = useMemo(() => new GeminiService(), []);

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

  return { status, generateFeedback };
};
