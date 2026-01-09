# dhis2-era5land-simple

A simple Python script to import ERA5-Land climate data into DHIS2, with Docker scheduling support.

This is a minimal, educational example showing how to:
- Read configuration from environment variables
- Run a Python script in Docker
- Schedule automated runs with cron

## Quick Start

### 1. Create `.env` file

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required settings:
- `CDSAPI_KEY` - Get from https://cds.climate.copernicus.eu/how-to-api
- `DHIS2_BASE_URL` - Your DHIS2 instance URL
- `DHIS2_USERNAME` - DHIS2 username
- `DHIS2_PASSWORD` - DHIS2 password
- `DHIS2_DATA_ELEMENT_ID` - Target data element ID

### 2. Run once

```bash
# With Docker
docker compose run --rm run

# Or locally
uv run python main.py
```

### 3. Run on schedule

```bash
# Set schedule in .env
echo "DHIS2_CRON=0 6 * * *" >> .env

# Start scheduler
docker compose up -d schedule

# View logs
docker compose logs -f schedule
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CDSAPI_KEY` | **Yes** | - | CDS API key |
| `DHIS2_BASE_URL` | **Yes** | - | DHIS2 instance URL |
| `DHIS2_USERNAME` | **Yes** | - | DHIS2 username |
| `DHIS2_PASSWORD` | **Yes** | - | DHIS2 password |
| `DHIS2_DATA_ELEMENT_ID` | **Yes** | - | Target data element |
| `DHIS2_START_DATE` | No | `2025-01-01` | Start date |
| `DHIS2_END_DATE` | No | `2025-01-07` | End date |
| `DHIS2_CRON` | No | `0 1 * * *` | Cron schedule |
| `DHIS2_TIMEZONE_OFFSET` | No | `0` | Timezone offset hours |
| `DHIS2_ORG_UNIT_LEVEL` | No | `2` | Organisation unit level |
| `DHIS2_DRY_RUN` | No | `false` | Don't actually import |

## Cron Schedule Examples

| Expression | Description |
|------------|-------------|
| `0 6 * * *` | Daily at 6:00 AM |
| `0 0 * * *` | Daily at midnight |
| `0 6 * * 1` | Weekly on Monday at 6:00 AM |
| `0 0 1 * *` | Monthly on the 1st |
| `*/30 * * * *` | Every 30 minutes (testing) |

Use [crontab.guru](https://crontab.guru/) to build cron expressions.

## How It Works

1. Script reads configuration from environment variables (loaded from `.env`)
2. Downloads ERA5-Land precipitation data from Copernicus Climate Data Store
3. Aggregates hourly data to daily values
4. Aggregates spatial data to DHIS2 organisation unit boundaries
5. Converts precipitation from meters to millimeters
6. Imports aggregated values into DHIS2

## Development

```bash
# Install dependencies
make install

# Run locally
make run

# Lint and format code
make lint

# Build Docker image
make docker-build
```
