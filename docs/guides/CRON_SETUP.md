# Cron Setup (Quick Reference)

## How it works

Bot stores `next_morning_reminder_at` (UTC) in DB → external cron calls `/cron/tick?token=SECRET` every 5 min → bot sends reminders

## Setup on Railway

### Option 1: cron-job.org (recommended)

1. Go to https://cron-job.org
2. Create cronjob:
   - URL: `https://your-app.railway.app/cron/tick?token=YOUR_TOKEN`
   - Schedule: `*/5 * * * *` (every 5 min)

### Option 2: GitHub Actions

`.github/workflows/cron.yml`:
```yaml
name: Cron Tick
on:
  schedule:
    - cron: '*/5 * * * *'
jobs:
  tick:
    runs-on: ubuntu-latest
    steps:
      - run: curl -f "https://your-app.railway.app/cron/tick?token=${{ secrets.CRON_TOKEN }}"
```

## Generate token

```bash
openssl rand -hex 32
```

Add to Railway Variables: `CRON_TOKEN=generated_token`

## Verify

```bash
# With token
curl "https://your-app.railway.app/cron/tick?token=YOUR_TOKEN"
# → {"status": "ok", "stats": {"morning_sent": 0, "evening_sent": 0}}

# Without token (should fail)
curl https://your-app.railway.app/cron/tick
# → {"error": "Unauthorized"}
```
