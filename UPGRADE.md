# Upgrade Notes: v1 to v2

This document describes the changes between the v1 (`main.py`) and v2 (`main_v2.py`) import scripts, issues encountered during the upgrade, and how they were resolved.

## Overview

The v2 script is based on the [import-era5-daily.ipynb](https://github.com/dhis2/climate-tools/blob/main/docs/workflows/import-era5/import-era5-daily.ipynb) notebook from the DHIS2 Climate Tools documentation. It introduces several improvements over the v1 implementation.

## Key Changes

### 1. Download API Change

| v1 | v2 |
|----|-----|
| `era5_land.hourly.get(year, month, ...)` | `era5_land.hourly.download(start, end, ...)` |
| Returns xarray directly | Saves files to disk, returns file paths |
| Per-month processing | Entire date range at once |
| No caching | File-based caching (reuses existing files) |

The v2 `download()` function is more efficient for recurring imports because it caches downloaded files to disk. Previously downloaded months are automatically skipped.

### 2. DHIS2 Client Initialization

```python
# v1
client = DHIS2Client(
    base_url=DHIS2_BASE_URL,
    username=DHIS2_USERNAME,
    password=DHIS2_PASSWORD,
)

# v2
cfg = ClientSettings(
    base_url=DHIS2_BASE_URL,
    username=DHIS2_USERNAME,
    password=DHIS2_PASSWORD,
)
client = DHIS2Client(settings=cfg)
```

The v2 approach uses a `ClientSettings` object, which is the newer pattern in `dhis2-client`.

### 3. Unit Conversion

```python
# v1 - hardcoded conversion
def meters_to_millimeters(value):
    return value * 1000

agg_df[value_col] = agg_df[value_col].apply(value_func)

# v2 - using metpy.units
from metpy.units import units

values_with_units = dataframe[value_col].values * units(from_units)
converted = values_with_units.to(to_units).magnitude
dataframe[value_col] = converted
```

The v2 approach uses `metpy.units` for proper unit handling, making unit conversion configurable via environment variables (`DHIS2_FROM_UNITS`, `DHIS2_TO_UNITS`).

### 4. Date Processing

v1 processes data month-by-month in a loop:
```python
for year, month in utils.time.iter_months(start_year, start_month, end_year, end_month):
    hourly_data = era5_land.hourly.get(year=year, month=month, ...)
    # process and import
```

v2 processes the entire date range at once:
```python
files = era5_land.hourly.download(start=import_start_date, end=end_date, ...)
ds_hourly = xr.open_mfdataset(files)
# process and import all at once
```

## Issues Encountered

### Issue 1: Missing `download()` function

**Problem:** The `era5_land.hourly.download()` function did not exist in the installed version of `dhis2eo`.

**Error:**
```
AttributeError: module 'dhis2eo.data.cds.era5_land.hourly' has no attribute 'download'
```

**Cause:** The `pyproject.toml` references `dhis2eo` from git, but uv had cached an older version that only had the `get()` function.

**Solution:** Force update the package:
```bash
uv lock --upgrade-package dhis2eo && uv sync
```

### Issue 2: Date Format Mismatch

**Problem:** The `download()` function expects ISO date format (`"2025-03-01"`) but the code was passing DHIS2 period format (`"202503"`).

**Error:**
```
ValueError: not enough values to unpack (expected 2, got 1)
```

**Cause:** The `analytics_latest_period_for_level()` API returns periods in DHIS2 format (e.g., `"20250315"` for daily or `"202503"` for monthly). The code was using this directly without conversion.

**Solution:** Convert DHIS2 period format to ISO date format:
```python
# Before (broken)
import_start_date = max(last_imported_month_string, start_date)

# After (fixed)
last_imported_date = f"{last_imported_month_string[:4]}-{last_imported_month_string[4:6]}-01"
import_start_date = max(last_imported_date, start_date)
```

## New Dependencies

| Package | Purpose |
|---------|---------|
| `papermill` | Run Jupyter notebooks from command line |
| `metpy` | Unit conversion with proper physical units |
| `ipykernel` | Required by papermill for notebook execution |

## New Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DHIS2_DOWNLOAD_FOLDER` | `./target/data` | Folder to cache downloaded ERA5 files |
| `DHIS2_DOWNLOAD_PREFIX` | `era5_hourly` | Prefix for cached files |
| `DHIS2_FROM_UNITS` | `m` | Source units for conversion |
| `DHIS2_TO_UNITS` | `mm` | Target units for conversion |

## Migration Guide

1. **Update dependencies:**
   ```bash
   uv lock --upgrade-package dhis2eo
   uv sync
   ```

2. **Optional: Add new environment variables** to your `.env` file if you want to customize:
   ```
   DHIS2_DOWNLOAD_FOLDER=./target/data
   DHIS2_DOWNLOAD_PREFIX=era5_hourly
   DHIS2_FROM_UNITS=m
   DHIS2_TO_UNITS=mm
   ```

3. **Run v2:**
   ```bash
   make run-v2
   ```

4. **Or run via papermill:**
   ```bash
   make run-notebook
   ```

## Backward Compatibility

The v1 script (`main.py`) is preserved and continues to work. Both scripts can coexist:

- `make run` - runs v1
- `make run-v2` - runs v2
- `make run-notebook` - runs the notebook via papermill

## Recommendations

- **For production Docker deployments:** Continue using v1 (`main.py`) as it's battle-tested
- **For local development/testing:** Use v2 for better caching and debugging
- **For interactive exploration:** Use the notebook directly or via papermill
