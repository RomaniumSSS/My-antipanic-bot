import type { Metadata, Viewport } from 'next';
import { TelegramProvider } from './providers';
import './globals.css';

export const metadata: Metadata = {
  title: 'Antipanic',
  description: 'Превращай большие цели в маленькие шаги',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  // Telegram Mini App colors
  themeColor: '#ffffff',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <head>
        {/* Telegram WebApp SDK */}
        <script src="https://telegram.org/js/telegram-web-app.js" async />
      </head>
      <body className="min-h-screen">
        <TelegramProvider>
          <main className="min-h-screen px-4 py-6">
            {children}
          </main>
        </TelegramProvider>
      </body>
    </html>
  );
}
