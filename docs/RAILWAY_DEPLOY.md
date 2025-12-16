# Railway Deploy (Quick Reference)

## Setup

1. **Create project**: Railway → "Deploy from GitHub repo"
2. **Add PostgreSQL**: "+ New" → "Add PostgreSQL"

## Environment Variables

```bash
# Required
BOT_TOKEN=your_bot_token
ENVIRONMENT=production
WEBHOOK_URL=https://your-app.railway.app

# AI Provider (choose one)
# Option 1: Anthropic Claude (default)
AI_PROVIDER=anthropic
ANTHROPIC_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514  # optional, defaults to this

# Option 2: OpenAI (fallback)
AI_PROVIDER=openai
OPENAI_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini

# Optional
ALLOWED_USER_IDS=123456789,987654321

# Auto-set by Railway
DATABASE_URL=(auto)
PORT=(auto)
```

## Verify

```bash
# Health check
curl https://your-app.railway.app/health

# Check webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

## Troubleshooting

- **DB errors**: Check `DATABASE_URL` in variables
- **Webhook not working**: Verify `WEBHOOK_URL` and `ENVIRONMENT=production`
- **Migrations**: `railway run aerich upgrade`

## Deploy

Push to `main` branch → auto-deploy
