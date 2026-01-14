# Upgrade Notes

This document describes the upgrade from the original import script to the new implementation based on the [import-era5-daily.ipynb](https://github.com/dhis2/climate-tools/blob/main/docs/workflows/import-era5/import-era5-daily.ipynb) notebook from the DHIS2 Climate Tools documentation.

## Breaking Change: dhis2eo API

**The `dhis2eo` library removed the `era5_land.hourly.get()` function and replaced it with `era5_land.hourly.download()`.**

This is a breaking change that required rewriting the import script. The old v1 script is no longer compatible with the latest `dhis2eo`.

```
# Error when running old script with new dhis2eo:
AttributeError: module 'dhis2eo.data.cds.era5_land.hourly' has no attribute 'get'
```

## Key Changes

### 1. Download API Change

| Old (removed) | New |
|---------------|-----|
| `era5_land.hourly.get(year, month, ...)` | `era5_land.hourly.download(start, end, ...)` |
| Returns xarray directly | Saves files to disk, returns file paths |
| Per-month processing | Entire date range at once |
| No caching | File-based caching (reuses existing files) |

The new `download()` function is more efficient for recurring imports because it caches downloaded files to disk. Previously downloaded months are automatically skipped.

### 2. DHIS2 Client Initialization

```python
# Old
client = DHIS2Client(
    base_url=DHIS2_BASE_URL,
    username=DHIS2_USERNAME,
    password=DHIS2_PASSWORD,
)

# New
cfg = ClientSettings(
    base_url=DHIS2_BASE_URL,
    username=DHIS2_USERNAME,
    password=DHIS2_PASSWORD,
)
client = DHIS2Client(settings=cfg)
```

The new approach uses a `ClientSettings` object, which is the newer pattern in `dhis2-client`.

### 3. Unit Conversion

```python
# Old - hardcoded conversion
def meters_to_millimeters(value):
    return value * 1000

agg_df[value_col] = agg_df[value_col].apply(value_func)

# New - using metpy.units
from metpy.units import units

values_with_units = dataframe[value_col].values * units(from_units)
converted = values_with_units.to(to_units).magnitude
dataframe[value_col] = converted
```

The new approach uses `metpy.units` for proper unit handling, making unit conversion configurable via environment variables (`DHIS2_FROM_UNITS`, `DHIS2_TO_UNITS`).

### 4. Date Processing

Old script processes data month-by-month in a loop:
```python
for year, month in utils.time.iter_months(start_year, start_month, end_year, end_month):
    hourly_data = era5_land.hourly.get(year=year, month=month, ...)
    # process and import
```

New script processes the entire date range at once:
```python
files = era5_land.hourly.download(start=import_start_date, end=end_date, ...)
ds_hourly = xr.open_mfdataset(files)
# process and import all at once
```

## Issues Encountered During Upgrade

### Issue 1: Cached dhis2eo version

**Problem:** The `era5_land.hourly.download()` function did not exist in the installed version of `dhis2eo`.

**Error:**
```
AttributeError: module 'dhis2eo.data.cds.era5_land.hourly' has no attribute 'download'
```

**Cause:** The `pyproject.toml` references `dhis2eo` from git, but uv had cached an older version that still had the `get()` function.

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

### Issue 3: Old script incompatible after dhis2eo update

**Problem:** After updating `dhis2eo` to get the new `download()` function, the old script stopped working because `get()` was removed.

**Error:**
```
AttributeError: module 'dhis2eo.data.cds.era5_land.hourly' has no attribute 'get'
```

**Cause:** The `dhis2eo` library made a breaking change - `get()` was replaced with `download()`, not added alongside it.

**Solution:** The old script was removed and the new implementation is now the only version. There is no way to maintain backward compatibility without pinning to an older `dhis2eo` version.

### Issue 4: Notebook missing parameters tag for papermill

**Problem:** Papermill couldn't inject parameters because the notebook lacked the `parameters` cell tag.

**Error:**
```
Passed unknown parameter: DHIS2_BASE_URL
Input notebook does not contain a cell with tag 'parameters'
```

**Solution:** Added `parameters` tag to the configuration cell in the notebook metadata.

### Issue 5: Same date format bug in notebook

**Problem:** The notebook had the same DHIS2 period format issue as the script.

**Solution:** Applied the same fix - convert `YYYYMM` to `YYYY-MM-DD` before passing to `download()`.

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

3. **Run:**
   ```bash
   make run
   ```

4. **Or run via papermill:**
   ```bash
   make run-notebook
   ```
