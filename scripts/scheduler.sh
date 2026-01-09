#!/bin/bash
set -e

# Default to daily at 1am if not set
DHIS2_CRON="${DHIS2_CRON:-0 1 * * *}"

# Export all DHIS2_ and CDSAPI_ env vars for cron job
printenv | grep -E '^(DHIS2_|CDSAPI_)' > /app/.env.cron

# Create crontab entry (redirect output to Docker stdout/stderr)
echo "$DHIS2_CRON cd /app && set -a && . /app/.env.cron && set +a && /usr/local/bin/uv run --no-sync python main.py >> /proc/1/fd/1 2>> /proc/1/fd/2" | crontab -

echo "Scheduler started with: $DHIS2_CRON"
crontab -l

# Run cron in foreground
exec cron -f
