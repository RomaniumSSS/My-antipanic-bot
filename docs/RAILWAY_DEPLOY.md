# Deploying Antipanic Bot to Railway

This guide explains how to deploy the Antipanic Bot to Railway with PostgreSQL and Redis.

## Prerequisites

1. GitHub account with bot repository
2. Railway account (https://railway.app)
3. Telegram Bot Token (from @BotFather)
4. OpenAI API Key

## Step 1: Create Railway Project

1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your `antipanic-bot` repository
4. Railway will auto-detect Python and create a service

## Step 2: Add PostgreSQL Database

1. In your Railway project, click "+ New"
2. Select "Database" → "Add PostgreSQL"
3. Railway will automatically create a `DATABASE_URL` environment variable

## Step 3: Add Redis (Optional, for production FSM)

1. In your Railway project, click "+ New"
2. Select "Database" → "Add Redis"
3. Railway will automatically set Redis connection vars

## Step 4: Configure Environment Variables

Go to your bot service → "Variables" tab and add:

### Required Variables

```bash
# Telegram
BOT_TOKEN=your_bot_token_from_botfather

# OpenAI
OPENAI_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini

# Environment
ENVIRONMENT=production

# Webhook (use Railway's auto-generated PUBLIC_URL)
WEBHOOK_URL=https://your-app-name.up.railway.app
```

### Optional Variables

```bash
# Alpha Testing (comma-separated user IDs, leave empty for open access)
ALLOWED_USER_IDS=123456789,987654321

# OpenAI Model (default: gpt-4o-mini)
OPENAI_MODEL=gpt-4o
```

**Note**: Railway auto-sets:
- `DATABASE_URL` (from PostgreSQL service)
- `REDIS_URL` (from Redis service)
- `PORT` (default 8080)

## Step 5: Deploy

1. Push code to GitHub (main branch)
2. Railway will auto-deploy on every push
3. Check deploy logs: Service → "Deployments" → Select latest → "View Logs"

## Step 6: Verify Deployment

### Check Health Endpoint

```bash
curl https://your-app-name.up.railway.app/health
# Should return: {"status": "ok"}
```

### Check Bot Status

1. Open Telegram
2. Send `/start` to your bot
3. Bot should respond

### Check Logs

Railway Dashboard → Service → Deployments → View Logs

Look for:
```
INFO - Using RedisStorage at ...
INFO - Database initialized
INFO - Scheduler started
INFO - Webhook set to: https://...
INFO - Starting webhook server on port 8080
```

## Troubleshooting

### Database Connection Errors

```bash
# Check DATABASE_URL is set
railway variables

# Verify PostgreSQL service is running
# Dashboard → PostgreSQL service → check status
```

### Webhook Not Receiving Updates

```bash
# Check webhook is set
curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo

# Should show:
# {
#   "url": "https://your-app.railway.app/webhook",
#   "has_custom_certificate": false,
#   "pending_update_count": 0,
#   ...
# }
```

If webhook is not set, check:
1. `WEBHOOK_URL` env var is correct
2. `ENVIRONMENT=production` is set
3. Bot startup logs show "Webhook set to: ..."

### Migrations Not Running

If you see database errors about missing tables:

```bash
# SSH into Railway container
railway run bash

# Run migrations manually
aerich upgrade

# Or check migration status
aerich history
```

### Redis Connection Errors

If using `MemoryStorage` instead of `RedisStorage`:

1. Check Redis service is running
2. Verify `REDIS_URL` is auto-set by Railway
3. Check logs for Redis connection messages

## Production Best Practices

### 1. Enable Redis for FSM Storage

Redis is required for production to persist bot states across restarts.

### 2. Monitor Logs

Railway Dashboard → Service → "Observability" → "Logs"

Watch for:
- Database connection errors
- OpenAI API rate limits
- Webhook delivery failures

### 3. Set Up Alerts (Optional)

Railway → Service → "Settings" → "Alerts"

Configure alerts for:
- Service crashes
- High memory usage
- Deployment failures

### 4. Database Backups

Railway automatically backs up PostgreSQL.

To restore:
1. Dashboard → PostgreSQL → "Backups"
2. Select backup → "Restore"

## Updating the Bot

```bash
# 1. Make changes locally
git add .
git commit -m "feat: add new feature"

# 2. Push to GitHub
git push origin main

# 3. Railway auto-deploys
# Check deployment status in Railway Dashboard
```

## Rolling Back

If deployment fails:

1. Railway Dashboard → Service → "Deployments"
2. Find last working deployment
3. Click "⋯" → "Redeploy"

## Cost Estimate

Railway Free Trial: $5 credit/month

- Bot service: ~$2-3/month
- PostgreSQL: ~$1-2/month
- Redis: ~$1/month

**Total**: ~$4-6/month (within free tier)

After trial, consider Railway Hobby plan ($5/month) or migrate to:
- **Render** (similar pricing)
- **Fly.io** (free tier available)
- **AWS Lambda** (serverless, complex setup)

## Next Steps

After deploying to Railway:

1. ✅ Bot running 24/7
2. ✅ PostgreSQL database
3. ⬜ **Stage 4**: Build TMA frontend (Next.js + Vercel)
4. ⬜ **Stage 5**: Add proactive notifications

See `docs/TMA_MIGRATION_PLAN.md` for full roadmap.
