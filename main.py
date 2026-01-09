"""Import ERA5-Land climate data into DHIS2.

This script downloads ERA5-Land data from the Copernicus Climate Data Store,
aggregates it to DHIS2 organisation units, and imports the values.

Configuration is loaded from environment variables (or .env file).
"""

import json
import os
from datetime import date

import geopandas as gpd
from dhis2_client import DHIS2Client
from dhis2eo import utils
from dhis2eo.data.cds import era5_land
from dhis2eo.integrations.pandas import dataframe_to_dhis2_json
from dotenv import load_dotenv
from earthkit import transforms

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
DHIS2_VARIABLE = os.getenv("DHIS2_VARIABLE", "total_precipitation")
DHIS2_VALUE_COL = os.getenv("DHIS2_VALUE_COL", "tp")

# Aggregation settings
DHIS2_TEMPORAL_AGGREGATION = os.getenv("DHIS2_TEMPORAL_AGGREGATION", "sum")
DHIS2_SPATIAL_AGGREGATION = os.getenv("DHIS2_SPATIAL_AGGREGATION", "mean")

# Date range
DHIS2_START_DATE = os.getenv("DHIS2_START_DATE", "2025-01-01")
DHIS2_END_DATE = os.getenv("DHIS2_END_DATE", "2025-01-07")

# Other settings
DHIS2_TIMEZONE_OFFSET = int(os.getenv("DHIS2_TIMEZONE_OFFSET", "0"))
DHIS2_ORG_UNIT_LEVEL = int(os.getenv("DHIS2_ORG_UNIT_LEVEL", "2"))
DHIS2_DRY_RUN = os.getenv("DHIS2_DRY_RUN", "false").lower() == "true"


# =============================================================================
# Value Transform
# =============================================================================


def meters_to_millimeters(value):
    """Convert precipitation from meters to millimeters."""
    return value * 1000


# =============================================================================
# Import Function
# =============================================================================


def import_era5_land_to_dhis2(
    client,
    variable,
    data_element_id,
    value_col,
    value_func,
    temporal_aggregation,
    spatial_aggregation,
    start_date,
    end_date,
    timezone_offset,
    org_unit_level,
    dry_run=False,
):
    """Download ERA5-Land data and import aggregated values into DHIS2."""
    variables = [variable]

    # Parse dates
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    start_year, start_month = start.year, start.month
    end_year, end_month = end.year, end.month

    # Get org units from DHIS2
    print("Fetching organisation units from DHIS2...")
    org_units_geojson = client.get_org_units_geojson(level=org_unit_level)
    org_units = gpd.read_file(json.dumps(org_units_geojson))
    print(f"Found {len(org_units)} organisation units at level {org_unit_level}")

    # Get last imported period
    last_imported_response = client.analytics_latest_period_for_level(de_uid=data_element_id, level=org_unit_level)
    last_imported_period = last_imported_response["existing"]
    last_imported_month_string = last_imported_period["id"][:6] if last_imported_period else None

    if last_imported_month_string:
        print(f"Last imported period: {last_imported_month_string}")
    else:
        print("No existing data found")

    # Process each month
    for year, month in utils.time.iter_months(start_year, start_month, end_year, end_month):
        month_string = utils.time.dhis2_period(year=year, month=month)
        print(f"\n{'=' * 50}")
        print(f"Processing {month_string}")

        # Check if import is needed
        needs_import = last_imported_month_string is None or (month_string >= last_imported_month_string)
        if not needs_import:
            print("Already imported, skipping...")
            continue

        # Download ERA5 data
        print("Downloading ERA5-Land data...")
        hourly_data = era5_land.hourly.get(year=year, month=month, variables=variables, bbox=org_units.total_bounds)

        # Temporal aggregation
        print("Aggregating temporally...")
        agg_time = transforms.temporal.daily_reduce(
            hourly_data[value_col],
            how=temporal_aggregation,
            time_shift={"hours": timezone_offset},
            remove_partial_periods=False,
        )

        # Spatial aggregation
        print("Aggregating to organisation units...")
        agg_org_units = transforms.spatial.reduce(
            agg_time,
            org_units,
            mask_dim="id",
            how=spatial_aggregation,
        )
        agg_df = agg_org_units.to_dataframe().reset_index()

        # Apply value transform
        print("Applying value transform...")
        agg_df[value_col] = agg_df[value_col].apply(value_func)

        # Create DHIS2 payload
        print(f"Creating payload with {len(agg_df)} values...")
        payload = dataframe_to_dhis2_json(
            df=agg_df,
            org_unit_col="id",
            period_col="valid_time",
            value_col=value_col,
            data_element_id=data_element_id,
        )

        # Import to DHIS2
        mode = "DRY RUN" if dry_run else "IMPORTING"
        print(f"{mode}...")
        res = client.post("/api/dataValueSets", json=payload, params={"dryRun": str(dry_run).lower()})
        print(f"Result: {res['response']['importCount']}")


# =============================================================================
# Main
# =============================================================================


def main():
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
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Create a .env file or set these environment variables.")
        exit(1)

    # Export CDS credentials for the cdsapi library
    os.environ["CDSAPI_URL"] = CDSAPI_URL
    os.environ["CDSAPI_KEY"] = CDSAPI_KEY

    # Create DHIS2 client
    client = DHIS2Client(
        base_url=DHIS2_BASE_URL,
        username=DHIS2_USERNAME,
        password=DHIS2_PASSWORD,
    )

    print(f"Starting import: {DHIS2_START_DATE} to {DHIS2_END_DATE}")
    print(f"Variable: {DHIS2_VARIABLE}")
    print(f"Dry run: {DHIS2_DRY_RUN}")

    # Run import
    import_era5_land_to_dhis2(
        client,
        variable=DHIS2_VARIABLE,
        data_element_id=DHIS2_DATA_ELEMENT_ID,
        value_col=DHIS2_VALUE_COL,
        value_func=meters_to_millimeters,
        temporal_aggregation=DHIS2_TEMPORAL_AGGREGATION,
        spatial_aggregation=DHIS2_SPATIAL_AGGREGATION,
        start_date=DHIS2_START_DATE,
        end_date=DHIS2_END_DATE,
        timezone_offset=DHIS2_TIMEZONE_OFFSET,
        org_unit_level=DHIS2_ORG_UNIT_LEVEL,
        dry_run=DHIS2_DRY_RUN,
    )

    print("\nDone!")


if __name__ == "__main__":
    main()
