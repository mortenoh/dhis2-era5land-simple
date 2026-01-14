# Automating ERA5-Land Imports

This guide explains how to set up automated, scheduled imports of ERA5-Land climate data into DHIS2. It builds on the [Import ERA5 Daily](https://climate-tools.dhis2.org/workflows/import-era5/import-era5-daily/) workflow, showing how to move from interactive notebook exploration to production-ready scheduled imports.

## Prerequisites

Before starting, ensure you have:

- Completed the [CDS API Authentication](https://climate-tools.dhis2.org/getting-data/climate-data-store/api-authentication/) setup
- A DHIS2 instance with a configured data element (see [Prepare Metadata](https://climate-tools.dhis2.org/import-data/prepare-metadata/))
- Basic familiarity with the [Import ERA5 Daily](https://climate-tools.dhis2.org/workflows/import-era5/import-era5-daily/) notebook

## 1) Understand the workflow

The import process follows these steps:

1. **Connect to DHIS2** - authenticate and fetch organisation unit geometries
2. **Check existing data** - determine what's already been imported
3. **Download ERA5-Land data** - fetch hourly precipitation from the CDS API
4. **Aggregate temporally** - convert hourly values to daily totals
5. **Aggregate spatially** - map grid cells to organisation unit boundaries
6. **Convert units** - transform meters to millimeters
7. **Import to DHIS2** - POST data values to the API

The [Import ERA5 Daily](https://climate-tools.dhis2.org/workflows/import-era5/import-era5-daily/) notebook walks through each step interactively. Run through it first to understand the process before automating.

## 2) Configure with environment variables

For automation, credentials and settings should be externalized using environment variables rather than hardcoded in scripts.

Create a `.env` file:

```bash
# Required - CDS API
CDSAPI_KEY=your-cds-api-key

# Required - DHIS2 connection
DHIS2_BASE_URL=https://your-dhis2-instance.org
DHIS2_USERNAME=your-username
DHIS2_PASSWORD=your-password
DHIS2_DATA_ELEMENT_ID=your-data-element-id

# Optional - customize behavior
DHIS2_START_DATE=2025-01-01
DHIS2_ORG_UNIT_LEVEL=2
DHIS2_DRY_RUN=true
```

The Python script loads these using `python-dotenv`:

```python
from dotenv import load_dotenv
import os

load_dotenv()

DHIS2_BASE_URL = os.getenv("DHIS2_BASE_URL")
DHIS2_DRY_RUN = os.getenv("DHIS2_DRY_RUN", "false").lower() == "true"
```

This approach allows:

- **Security** - credentials stay out of version control
- **Flexibility** - different settings per environment (dev/staging/prod)
- **Docker compatibility** - containers can use `--env-file` flag

## 3) Run the import script

A complete import script is available at [dhis2-era5land-simple](https://github.com/mortenoh/dhis2-era5land-simple).

```bash
# Clone the repository
git clone https://github.com/mortenoh/dhis2-era5land-simple.git
cd dhis2-era5land-simple

# Create .env file with your settings
cp .env.example .env
# Edit .env with your credentials

# Install dependencies
uv sync

# Test with dry-run mode
make run
```

The script will:

- Skip months that have already been imported
- Cache downloaded ERA5 files locally (in `target/data/`)
- Log progress and import counts

## 4) Schedule with Docker and cron

For production use, run imports automatically on a schedule using Docker.

### Start the scheduler

```bash
# Add schedule to .env (daily at 6 AM)
echo "DHIS2_CRON=0 6 * * *" >> .env

# Start using pre-built image
docker compose -f compose.ghcr.yml up -d schedule

# View logs
docker compose logs -f schedule
```

### Cron expression examples

| Expression | Description |
|------------|-------------|
| `0 6 * * *` | Daily at 6:00 AM |
| `0 1 * * *` | Daily at 1:00 AM |
| `0 0 * * 0` | Weekly on Sunday at midnight |
| `0 0 1 * *` | Monthly on the 1st |

Use [crontab.guru](https://crontab.guru/) to build expressions.

### How the scheduler works

The scheduler container:

1. Reads `DHIS2_CRON` from environment variables
2. Creates a crontab entry that runs `main.py`
3. Forwards output to Docker logs for monitoring
4. Runs continuously, executing the import on schedule

## 5) Run notebooks with papermill

Alternatively, run the original notebook directly using [papermill](https://papermill.readthedocs.io/):

```bash
# Run notebook with parameters from .env (outputs to stdout)
make run-notebook
```

This uses `scripts/run_notebook.py` which:

1. Loads configuration from `.env` file
2. Passes parameters to papermill (DHIS2 credentials, data element ID, etc.)
3. Streams output to stdout for logging (no output file created)
4. Shares the cache folder with `main.py` for faster subsequent runs

Papermill is useful for:

- Running notebooks in CI/CD pipelines
- Testing with different configurations
- Keeping the notebook as the source of truth

## Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `CDSAPI_KEY` | - | CDS API key (required) |
| `DHIS2_BASE_URL` | - | DHIS2 instance URL (required) |
| `DHIS2_USERNAME` | - | DHIS2 username (required) |
| `DHIS2_PASSWORD` | - | DHIS2 password (required) |
| `DHIS2_DATA_ELEMENT_ID` | - | Target data element (required) |
| `DHIS2_START_DATE` | `2025-01-01` | Import start date |
| `DHIS2_END_DATE` | today | Import end date |
| `DHIS2_ORG_UNIT_LEVEL` | `2` | Organisation unit level |
| `DHIS2_TIMEZONE_OFFSET` | `0` | Hours offset from UTC |
| `DHIS2_DRY_RUN` | `false` | Test without importing |
| `DHIS2_DOWNLOAD_FOLDER` | `./target/data` | Cache folder for ERA5 files |
| `DHIS2_CRON` | `0 1 * * *` | Cron schedule expression |

## Troubleshooting

- **"No new data files to process"** - All data for the date range is already imported. Extend `DHIS2_END_DATE` or check `DHIS2_START_DATE`.

- **CDS API errors** - Verify your API key and that you've accepted the [ERA5-Land terms](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land).

- **DHIS2 authentication errors** - Check credentials work in the web interface and that the user has data import permissions.

- **Import count is 0** - The data element may not be assigned to a dataset, or the organisation units may not match.

## Further reading

- [Import ERA5 Daily Notebook](https://climate-tools.dhis2.org/workflows/import-era5/import-era5-daily/)
- [Basics of Importing with Python Client](https://climate-tools.dhis2.org/import-data/basics-python-client-import/)
- [Prepare Metadata](https://climate-tools.dhis2.org/import-data/prepare-metadata/)
- [ERA5-Land Dataset](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land)
