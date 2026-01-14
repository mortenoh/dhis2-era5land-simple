# Tutorial: From Notebook to Scheduled Imports

This tutorial walks through the journey from exploring climate data in a Jupyter notebook to running automated, scheduled imports into DHIS2.

## Overview

The workflow has three stages:

1. **Explore** - Use the notebook interactively to understand the data and workflow
2. **Automate** - Convert to a script with environment variable configuration
3. **Schedule** - Run automatically on a recurring basis using Docker and cron

## Prerequisites

Before starting, make sure you have:

- [CDS API access](https://climate-tools.dhis2.org/getting-data/climate-data-store/api-authentication/) configured
- A DHIS2 instance with a data element for precipitation
- [uv](https://docs.astral.sh/uv/) installed for Python dependency management
- Docker installed (for scheduling)

## Stage 1: Explore with the Notebook

The best way to understand the workflow is to run through the notebook interactively.

### Option A: Run on climate-tools.dhis2.org

The easiest option is to use the hosted JupyterHub:

1. Go to [climate-tools.dhis2.org](https://climate-tools.dhis2.org)
2. Open the [Import ERA5 Daily](https://climate-tools.dhis2.org/workflows/import-era5/import-era5-daily/) notebook
3. Follow along, modifying parameters for your DHIS2 instance

### Option B: Run locally with papermill

If you prefer running locally:

```bash
# Clone this repo
git clone https://github.com/mortenoh/dhis2-era5land-simple.git
cd dhis2-era5land-simple

# Install dependencies
uv sync

# Run the notebook (outputs to target/output/)
make run-notebook
```

The notebook is at `notebooks/import-era5-daily.ipynb`. You can also open it in JupyterLab:

```bash
uv run jupyter lab notebooks/import-era5-daily.ipynb
```

### What the notebook does

The notebook demonstrates the complete workflow:

```
┌─────────────────────────────────────────────────────────────┐
│  1. Connect to DHIS2                                        │
│     - Authenticate with username/password                   │
│     - Fetch organisation unit geometries                    │
│     - Check what data already exists                        │
├─────────────────────────────────────────────────────────────┤
│  2. Download ERA5-Land data                                 │
│     - Request hourly precipitation from CDS API             │
│     - Cache files locally to avoid re-downloading           │
├─────────────────────────────────────────────────────────────┤
│  3. Aggregate temporally                                    │
│     - Convert hourly → daily values                         │
│     - Sum precipitation for each day                        │
├─────────────────────────────────────────────────────────────┤
│  4. Aggregate spatially                                     │
│     - Map grid cells to organisation unit boundaries        │
│     - Calculate mean value for each org unit                │
├─────────────────────────────────────────────────────────────┤
│  5. Convert units                                           │
│     - Transform meters → millimeters                        │
├─────────────────────────────────────────────────────────────┤
│  6. Import to DHIS2                                         │
│     - Create JSON payload                                   │
│     - POST to /api/dataValueSets                            │
└─────────────────────────────────────────────────────────────┘
```

## Stage 2: Automate with Environment Variables

Once you understand the workflow, the next step is making it configurable and repeatable.

### Why environment variables?

Hardcoding credentials and settings in a script is problematic:

- **Security risk** - credentials might end up in version control
- **Inflexible** - changing settings requires editing code
- **Environment-specific** - different settings for dev/staging/prod

Environment variables solve these issues by externalizing configuration.

### The .env file

Create a `.env` file with your settings:

```bash
cp .env.example .env
```

Edit `.env` with your values:

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
DHIS2_END_DATE=2025-12-31
DHIS2_DRY_RUN=true  # Set to false for actual imports
```

### How the script loads configuration

The script uses `python-dotenv` to load the `.env` file:

```python
from dotenv import load_dotenv
import os

# Load .env file into environment
load_dotenv()

# Read values with defaults
DHIS2_BASE_URL = os.getenv("DHIS2_BASE_URL")
DHIS2_DRY_RUN = os.getenv("DHIS2_DRY_RUN", "false").lower() == "true"
```

This pattern allows:
- Local development with `.env` file
- Production deployment with actual environment variables
- Docker containers with `--env-file` flag

### Test locally

```bash
# Run with dry-run mode first
make run

# Check the output, then set DHIS2_DRY_RUN=false for actual imports
```

## Stage 3: Schedule with Docker and Cron

For production use, you want imports to run automatically.

### Why Docker?

- **Isolation** - dependencies don't conflict with system packages
- **Reproducibility** - same environment everywhere
- **Easy deployment** - single image contains everything needed

### The scheduler

This repo includes a scheduler that runs the import on a cron schedule:

```bash
# Add schedule to .env
echo "DHIS2_CRON=0 6 * * *" >> .env  # Daily at 6 AM

# Start the scheduler
docker compose up -d schedule

# View logs
docker compose logs -f schedule
```

### How it works

The `scripts/scheduler.sh` script:

1. Reads `DHIS2_CRON` from environment (default: `0 1 * * *`)
2. Creates a crontab entry that runs `main.py`
3. Forwards output to Docker logs
4. Runs cron in the foreground to keep the container alive

```bash
# Example crontab entry created by scheduler.sh:
0 6 * * * cd /app && uv run --no-sync python main.py >> /proc/1/fd/1 2>&1
```

### Cron expression examples

| Expression | Description |
|------------|-------------|
| `0 6 * * *` | Daily at 6:00 AM |
| `0 1 * * *` | Daily at 1:00 AM |
| `0 0 * * 0` | Weekly on Sunday at midnight |
| `0 0 1 * *` | Monthly on the 1st |
| `*/30 * * * *` | Every 30 minutes (for testing) |

Use [crontab.guru](https://crontab.guru/) to build expressions.

### Using the pre-built image

For easier deployment, use the pre-built image from GitHub Container Registry:

```bash
# Run once
docker compose -f compose.ghcr.yml run --rm run

# Start scheduler
docker compose -f compose.ghcr.yml up -d schedule
```

## Complete Setup Example

Here's a complete example from scratch:

```bash
# 1. Clone the repo
git clone https://github.com/mortenoh/dhis2-era5land-simple.git
cd dhis2-era5land-simple

# 2. Create .env file
cat > .env << 'EOF'
CDSAPI_KEY=your-cds-api-key
DHIS2_BASE_URL=https://play.im.dhis2.org/stable-2-42-3-1
DHIS2_USERNAME=admin
DHIS2_PASSWORD=district
DHIS2_DATA_ELEMENT_ID=Ngy4iWUXwYb
DHIS2_START_DATE=2025-01-01
DHIS2_DRY_RUN=true
DHIS2_CRON=0 6 * * *
EOF

# 3. Test locally first
uv sync
make run

# 4. If everything looks good, disable dry-run
sed -i '' 's/DHIS2_DRY_RUN=true/DHIS2_DRY_RUN=false/' .env

# 5. Run actual import
make run

# 6. Start scheduled imports
docker compose -f compose.ghcr.yml up -d schedule

# 7. Check it's running
docker compose logs -f schedule
```

## Troubleshooting

### "No new data files to process"

This means all data for the date range has already been imported. Either:
- Extend `DHIS2_END_DATE` to include more recent dates
- Change `DHIS2_START_DATE` to an earlier date

### CDS API errors

- Verify your API key at [cds.climate.copernicus.eu](https://cds.climate.copernicus.eu/)
- Check you've accepted the terms for ERA5-Land dataset
- The API has rate limits - large requests may be queued

### DHIS2 authentication errors

- Verify credentials work in the DHIS2 web interface
- Check the user has permission to import data values
- Ensure the data element ID exists and is accessible

## Further Reading

- [DHIS2 Climate Tools Documentation](https://climate-tools.dhis2.org/)
- [ERA5-Land Dataset](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land)
- [CDS API Authentication Guide](https://climate-tools.dhis2.org/getting-data/climate-data-store/api-authentication/)
- [dhis2eo Library](https://github.com/dhis2/dhis2eo)
- [earthkit Documentation](https://earthkit.readthedocs.io/)
