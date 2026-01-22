"""Import ERA5-Land climate data into DHIS2 (v2).

This script downloads ERA5-Land data from the Copernicus Climate Data Store,
aggregates it to DHIS2 organisation units, and imports the values.

This is the v2 version that uses file-based caching and metpy for unit conversion.
Based on the import-era5-daily notebook from dhis2/climate-tools.

Configuration is loaded from environment variables (or .env file).
"""

import json
import logging
import os
from datetime import date

import geopandas as gpd
import xarray as xr
from dhis2_client import DHIS2Client
from dhis2_client.settings import ClientSettings
from dotenv import load_dotenv
from earthkit import transforms
from metpy.units import units

from dhis2eo.data.cds import era5_land
from dhis2eo.integrations.pandas import dataframe_to_dhis2_json

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Configuration (from environment variables)
# =============================================================================

# CDS API credentials (required)
CDSAPI_URL = os.getenv("CDSAPI_URL", "https://cds.climate.copernicus.eu/api")
CDSAPI_KEY = os.getenv("CDSAPI_KEY")

# DHIS2 connection (required)
DHIS2_BASE_URL = os.getenv("DHIS2_BASE_URL")
DHIS2_USERNAME = os.getenv("DHIS2_USERNAME")
DHIS2_PASSWORD = os.getenv("DHIS2_PASSWORD")

# DHIS2 data element to import into (required)
DHIS2_DATA_ELEMENT_ID = os.getenv("DHIS2_DATA_ELEMENT_ID")

# ERA5 variable configuration
# DHIS2_VARIABLE: CDS catalogue name (e.g., "total_precipitation")
# DHIS2_VALUE_COL: Column name in downloaded xarray dataset (e.g., "tp")
# These are coupled - the value_col depends on which variable you download
DHIS2_VARIABLE = os.getenv("DHIS2_VARIABLE", "total_precipitation")
DHIS2_VALUE_COL = os.getenv("DHIS2_VALUE_COL", "tp")
DHIS2_IS_CUMULATIVE = os.getenv("DHIS2_IS_CUMULATIVE", True)  # maybe this should be default False, since it's primarily for precipitation

# Unit conversion
DHIS2_FROM_UNITS = os.getenv("DHIS2_FROM_UNITS", "m")
DHIS2_TO_UNITS = os.getenv("DHIS2_TO_UNITS", "mm")

# Aggregation settings
DHIS2_TEMPORAL_AGGREGATION = os.getenv("DHIS2_TEMPORAL_AGGREGATION", "sum")
DHIS2_SPATIAL_AGGREGATION = os.getenv("DHIS2_SPATIAL_AGGREGATION", "mean")

# Date range
DHIS2_START_DATE = os.getenv("DHIS2_START_DATE", "2025-01-01")
DHIS2_END_DATE = os.getenv("DHIS2_END_DATE", date.today().isoformat())

# Download settings (v2 specific - file-based caching)
DHIS2_DOWNLOAD_FOLDER = os.getenv("DHIS2_DOWNLOAD_FOLDER", "./target/data")
DHIS2_DOWNLOAD_PREFIX = os.getenv("DHIS2_DOWNLOAD_PREFIX", "era5_hourly")

# Other settings
DHIS2_TIMEZONE_OFFSET = int(os.getenv("DHIS2_TIMEZONE_OFFSET", "0"))
DHIS2_ORG_UNIT_LEVEL = int(os.getenv("DHIS2_ORG_UNIT_LEVEL", "2"))
DHIS2_DRY_RUN = os.getenv("DHIS2_DRY_RUN", "true").lower() == "true"


# =============================================================================
# Import Function
# =============================================================================


def import_era5_land_to_dhis2(
    client: DHIS2Client,
    variable: str,
    data_element_id: str,
    value_col: str,
    is_cumulative: str,
    from_units: str,
    to_units: str,
    temporal_aggregation: str,
    spatial_aggregation: str,
    start_date: str,
    end_date: str,
    download_folder: str,
    download_prefix: str,
    timezone_offset: int,
    org_unit_level: int,
    dry_run: bool = False,
) -> None:
    """Download ERA5-Land data and import aggregated values into DHIS2."""
    variables = [variable]

    # Get org units from DHIS2
    logger.info("Fetching organisation units from DHIS2...")
    org_units_geojson = client.get_org_units_geojson(level=org_unit_level)
    org_units = gpd.read_file(json.dumps(org_units_geojson))
    logger.info("Found %d organisation units at level %d", len(org_units), org_unit_level)

    # Get last imported period to determine where to start
    last_imported_response = client.analytics_latest_period_for_level(de_uid=data_element_id, level=org_unit_level)
    last_imported_period = last_imported_response["existing"]
    last_imported_month_string = last_imported_period["id"][:6] if last_imported_period else None

    if last_imported_month_string:
        logger.info("Last imported period: %s", last_imported_month_string)
        # Convert DHIS2 period format (YYYYMM) to ISO date format (YYYY-MM-DD)
        last_imported_date = f"{last_imported_month_string[:4]}-{last_imported_month_string[4:6]}-01"
        # Start from the later of configured start date or last imported month
        import_start_date = max(last_imported_date, start_date)
    else:
        logger.info("No existing data found")
        import_start_date = start_date

    logger.info("Import will start at %s", import_start_date)
    logger.info("Import will end at %s", end_date)

    # Download ERA5 data (with file-based caching)
    logger.info("Downloading ERA5-Land data...")
    os.makedirs(download_folder, exist_ok=True)
    files = era5_land.hourly.download(
        start=import_start_date,
        end=end_date,
        bbox=tuple(org_units.total_bounds),  # type: ignore[arg-type]
        dirname=download_folder,
        prefix=download_prefix,
        variables=variables,
    )

    if not files:
        logger.info("No new data files to process")
        return

    logger.info("Downloaded %d files", len(files))

    # Load all files into a single dataset
    logger.info("Loading data from files...")
    ds_hourly = xr.open_mfdataset(files)

    # Cumulative variables such as precipitation
    # ...have to be de-accumulated before proceeding
    if is_cumulative:
        logger.info('Converting cumulative to incremental variable...')
        # convert cumulative to diffs
        ds_diffs = ds_hourly.diff(dim='valid_time')
        # replace negative diffs with original cumulative (the hours where accumulation resets)
        ds_diffs = xr.where(ds_diffs < 0, ds_hourly.isel(valid_time=slice(1, None)), ds_diffs)
        ds_hourly = ds_diffs

    # Temporal aggregation
    logger.info("Aggregating temporally...")
    ds_daily = transforms.temporal.daily_reduce(
        ds_hourly[value_col],
        how=temporal_aggregation,
        time_shift={"hours": timezone_offset},
        remove_partial_periods=False,
    )

    # Spatial aggregation
    logger.info("Aggregating to organisation units...")
    ds_org_units = transforms.spatial.reduce(
        ds_daily,
        org_units,
        mask_dim="id",
        how=spatial_aggregation,
    )
    dataframe = ds_org_units.to_dataframe().reset_index()

    # Apply unit conversion using metpy
    if to_units != from_units:
        logger.info("Applying unit conversion from %s to %s...", from_units, to_units)
        values_with_units = dataframe[value_col].values * units(from_units)
        converted = values_with_units.to(to_units).magnitude
        dataframe[value_col] = converted
    else:
        logger.info("No unit conversion needed")

    # Create DHIS2 payload
    logger.info("Creating payload with %d values...", len(dataframe))
    payload = dataframe_to_dhis2_json(
        df=dataframe,
        org_unit_col="id",
        period_col="valid_time",
        value_col=value_col,
        data_element_id=data_element_id,
    )

    # Import to DHIS2
    mode = "DRY RUN" if dry_run else "IMPORTING"
    logger.info("%s...", mode)
    res = client.post("/api/dataValueSets", json=payload, params={"dryRun": str(dry_run).lower()})
    logger.info("Result: %s", res["response"]["importCount"])


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """Main entry point."""
    # Validate required settings
    missing = []
    if not CDSAPI_KEY:
        missing.append("CDSAPI_KEY")
    if not DHIS2_BASE_URL:
        missing.append("DHIS2_BASE_URL")
    if not DHIS2_USERNAME:
        missing.append("DHIS2_USERNAME")
    if not DHIS2_PASSWORD:
        missing.append("DHIS2_PASSWORD")
    if not DHIS2_DATA_ELEMENT_ID:
        missing.append("DHIS2_DATA_ELEMENT_ID")

    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Create a .env file or set these environment variables.")
        exit(1)

    # Export CDS credentials for the cdsapi library
    os.environ["CDSAPI_URL"] = CDSAPI_URL
    os.environ["CDSAPI_KEY"] = CDSAPI_KEY  # type: ignore[assignment]

    # Assert required values are not None (validated above)
    assert DHIS2_BASE_URL is not None
    assert DHIS2_USERNAME is not None
    assert DHIS2_PASSWORD is not None

    # Create DHIS2 client using ClientSettings (v2 approach)
    cfg = ClientSettings(
        base_url=DHIS2_BASE_URL,
        username=DHIS2_USERNAME,
        password=DHIS2_PASSWORD,
    )
    client = DHIS2Client(settings=cfg)

    # Verify connection
    info = client.get_system_info()
    logger.info("Connected to DHIS2 version: %s", info["version"])

    logger.info("Starting import: %s to %s", DHIS2_START_DATE, DHIS2_END_DATE)
    logger.info("Variable: %s", DHIS2_VARIABLE)
    logger.info("Download folder: %s", DHIS2_DOWNLOAD_FOLDER)
    logger.info("Dry run: %s", DHIS2_DRY_RUN)

    # Run import (DHIS2_DATA_ELEMENT_ID is validated above so assert it's not None)
    assert DHIS2_DATA_ELEMENT_ID is not None
    import_era5_land_to_dhis2(
        client,
        variable=DHIS2_VARIABLE,
        data_element_id=DHIS2_DATA_ELEMENT_ID,
        value_col=DHIS2_VALUE_COL,
        is_cumulative=DHIS2_IS_CUMULATIVE,
        from_units=DHIS2_FROM_UNITS,
        to_units=DHIS2_TO_UNITS,
        temporal_aggregation=DHIS2_TEMPORAL_AGGREGATION,
        spatial_aggregation=DHIS2_SPATIAL_AGGREGATION,
        start_date=DHIS2_START_DATE,
        end_date=DHIS2_END_DATE,
        download_folder=DHIS2_DOWNLOAD_FOLDER,
        download_prefix=DHIS2_DOWNLOAD_PREFIX,
        timezone_offset=DHIS2_TIMEZONE_OFFSET,
        org_unit_level=DHIS2_ORG_UNIT_LEVEL,
        dry_run=DHIS2_DRY_RUN,
    )

    logger.info("Done!")


if __name__ == "__main__":
    main()
