#!/usr/bin/env python3
"""Run the ERA5 import notebook with parameters from .env file."""

import os
import subprocess
import sys
from datetime import date

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Validate required variables
required = ["DHIS2_BASE_URL", "DHIS2_USERNAME", "DHIS2_PASSWORD", "DHIS2_DATA_ELEMENT_ID", "CDSAPI_KEY"]
missing = [v for v in required if not os.getenv(v)]
if missing:
    sys.exit(f"Missing required environment variables: {', '.join(missing)}")

# Export CDS API credentials for earthkit/cdsapi
cdsapi_key = os.getenv("CDSAPI_KEY")
if cdsapi_key:
    os.environ["CDSAPI_URL"] = os.getenv("CDSAPI_URL", "https://cds.climate.copernicus.eu/api")
    os.environ["CDSAPI_KEY"] = cdsapi_key

# Build papermill command
notebook_input = "notebooks/import-era5-daily.ipynb"

# Parameters to pass to the notebook
# Note: notebook uses IMPORT_START_DATE/IMPORT_END_DATE, .env uses DHIS2_START_DATE/DHIS2_END_DATE
params = [
    "-p",
    "DHIS2_BASE_URL",
    os.getenv("DHIS2_BASE_URL", ""),
    "-p",
    "DHIS2_USERNAME",
    os.getenv("DHIS2_USERNAME", ""),
    "-p",
    "DHIS2_PASSWORD",
    os.getenv("DHIS2_PASSWORD", ""),
    "-p",
    "DHIS2_DATA_ELEMENT_ID",
    os.getenv("DHIS2_DATA_ELEMENT_ID", ""),
    "-p",
    "DHIS2_ORG_UNIT_LEVEL",
    os.getenv("DHIS2_ORG_UNIT_LEVEL", "2"),
    "-p",
    "DHIS2_DRY_RUN",
    os.getenv("DHIS2_DRY_RUN", "true"),
    "-p",
    "DHIS2_TIMEZONE_OFFSET",
    os.getenv("DHIS2_TIMEZONE_OFFSET", "0"),
    "-p",
    "DOWNLOAD_FOLDER",
    os.getenv("DHIS2_DOWNLOAD_FOLDER", "./target/data"),
    "-p",
    "IMPORT_START_DATE",
    os.getenv("DHIS2_START_DATE", "2025-01-01"),
    "-p",
    "IMPORT_END_DATE",
    os.getenv("DHIS2_END_DATE", date.today().isoformat()),
]

# Output to /dev/null, log to stdout
cmd = ["papermill", notebook_input, "/dev/null", "--log-output"] + params

result = subprocess.run(cmd, env=os.environ)
sys.exit(result.returncode)
