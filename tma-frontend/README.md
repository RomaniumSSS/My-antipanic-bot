# Antipanic Bot - Telegram Mini App

Next.js frontend for Antipanic Bot Telegram Mini App.

## Features

- User profile with XP, level, and streak
- Micro-action generator with AI-powered suggestions
- Real-time integration with FastAPI backend
- Telegram WebApp SDK integration
- Tailwind CSS styling with Telegram theme support

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Authentication**: Telegram WebApp SDK
- **API**: FastAPI backend

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Running FastAPI backend (see `../src/interfaces/api/`)

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local
```

### Configuration

Edit `.env.local`:

```bash
# FastAPI backend URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Development

```bash
# Run development server
npm run dev
```

Open http://localhost:3000 in your browser.

### Testing in Telegram

To test as a Telegram Mini App:

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Get your bot token
3. Use [@BotFather](https://t.me/BotFather) to set up a Web App:
   ```
   /newapp
   /setapptitle - Antipanic Bot
   /setappshortname - antipanic
   /setappurl - https://your-vercel-app.vercel.app
   ```
4. Open the app in Telegram

### Building for Production

```bash
# Build
npm run build

# Run production server
npm start
```

## Deployment

### Deploy to Vercel

1. **Install Vercel CLI** (if not already):
   ```bash
   npm i -g vercel
   ```

2. **Deploy**:
   ```bash
   cd tma-frontend
   vercel
   ```

3. **Set environment variables** in Vercel dashboard:
   - `NEXT_PUBLIC_API_URL` - Your FastAPI backend URL (e.g., `https://your-app.railway.app`)

4. **Update Bot Web App URL** via [@BotFather](https://t.me/BotFather):
   ```
   /setappurl - https://your-vercel-app.vercel.app
   ```

### Deploy via Vercel Dashboard

1. Connect your GitHub repo to Vercel
2. Set root directory to `tma-frontend`
3. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = your FastAPI backend URL
4. Deploy

## Project Structure

```
tma-frontend/
├── app/
│   ├── layout.tsx      # Root layout with Telegram SDK
│   ├── page.tsx        # Main page (profile + microhits)
│   └── globals.css     # Global styles with Telegram theme
├── lib/
│   ├── api.ts          # FastAPI client
│   └── telegram.ts     # Telegram WebApp utilities
├── components/         # React components (future)
├── public/             # Static assets
└── ...config files
```

## API Integration

The app uses the following FastAPI endpoints:

- `GET /api/me` - Get user profile
- `POST /api/microhit/generate` - Generate micro-action options
- `POST /api/microhit/complete` - Complete a micro-action

Authentication is handled via Telegram WebApp `initData` sent in `X-Telegram-Init-Data` header.

## Development Tips

### Running with Local Backend

1. Start FastAPI backend:
   ```bash
   # In project root
   python run_api.py
   ```

2. Start Next.js dev server:
   ```bash
   cd tma-frontend
   npm run dev
   ```

3. Open http://localhost:3000

**Note**: When testing locally, the Telegram WebApp SDK won't work outside of Telegram. Use the dev endpoints in FastAPI (`/dev/*`) for testing without auth.

### Telegram Theme Variables

The app uses Telegram theme CSS variables:

- `var(--tg-theme-bg-color)` - Background color
- `var(--tg-theme-text-color)` - Text color
- `var(--tg-theme-button-color)` - Primary button color
- `var(--tg-theme-hint-color)` - Hint/secondary text color

These are automatically provided by Telegram WebApp SDK.

## Troubleshooting

### "This app only works inside Telegram"

This error appears when opening the app outside of Telegram. This is expected behavior for a Telegram Mini App.

**Solutions**:
- Open the app via your Telegram bot
- For local testing, modify the code to bypass Telegram check temporarily
- Use FastAPI dev endpoints for API testing

### API Connection Failed

Check:
1. FastAPI backend is running
2. `NEXT_PUBLIC_API_URL` is correct
3. CORS is configured in FastAPI (`main.py`)
4. Network connectivity

### Build Errors

```bash
# Clear Next.js cache
rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Rebuild
npm run build
```

## Next Steps

After basic deployment:

1. Add more pages (stats, history, goals)
2. Improve UI/UX with animations
3. Add error boundaries
4. Implement loading states
5. Add analytics

## License

MIT
