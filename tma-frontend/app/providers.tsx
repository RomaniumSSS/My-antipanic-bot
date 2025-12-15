'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { initTelegramWebApp, type TelegramWebApp } from '@/lib/telegram';

interface TelegramContextType {
  webApp: TelegramWebApp | null;
  isReady: boolean;
  isInTelegram: boolean;
}

const TelegramContext = createContext<TelegramContextType>({
  webApp: null,
  isReady: false,
  isInTelegram: false,
});

export function useTelegram() {
  return useContext(TelegramContext);
}

interface TelegramProviderProps {
  children: ReactNode;
}

export function TelegramProvider({ children }: TelegramProviderProps) {
  const [webApp, setWebApp] = useState<TelegramWebApp | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let mounted = true;
    let checkInterval: NodeJS.Timeout | null = null;
    let timeoutId: NodeJS.Timeout | null = null;

    // Initialize Telegram WebApp
    const initializeTelegram = () => {
      if (!mounted) return;
      
      const tg = initTelegramWebApp();
      setWebApp(tg);
      setIsReady(true);

      // Debug mode: log initialization
      if (process.env.NEXT_PUBLIC_DEBUG === 'true') {
        console.log('[TMA] Initialized:', {
          isInTelegram: !!tg,
          platform: tg?.platform,
          version: tg?.version,
          colorScheme: tg?.colorScheme,
        });
      }
    };

    // Check if SDK is already loaded
    if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
      initializeTelegram();
    } else {
      // Wait for SDK to load (max 500ms, then assume not in Telegram)
      checkInterval = setInterval(() => {
        if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
          if (checkInterval) clearInterval(checkInterval);
          if (timeoutId) clearTimeout(timeoutId);
          initializeTelegram();
        }
      }, 50);

      // Timeout after 500ms (not in Telegram)
      timeoutId = setTimeout(() => {
        if (checkInterval) clearInterval(checkInterval);
        if (mounted) {
          console.log('[TMA] Not in Telegram, showing demo mode');
          setIsReady(true);
        }
      }, 500);
    }

    return () => {
      mounted = false;
      if (checkInterval) clearInterval(checkInterval);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, []); // Empty deps — run once on mount

  const value: TelegramContextType = {
    webApp,
    isReady,
    isInTelegram: webApp !== null,
  };

  return (
    <TelegramContext.Provider value={value}>
      {children}
    </TelegramContext.Provider>
  );
}
