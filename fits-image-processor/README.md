# fits-image-processor

CLI tool for processing FITS astronomical images. Handles the standard CCD reduction pipeline (bias/dark/flat correction), image stacking, thumbnail generation, and metadata cataloging.

## Commands

```bash
pip install -r requirements.txt && pip install -e .

# inspect headers, WCS, image stats
python -m fits_processor inspect observation.fits

# CCD reduction
python -m fits_processor normalize science.fits --bias bias.fits --dark dark.fits --flat flat.fits -o reduced.fits

# median-stack multiple frames (rejects cosmic rays)
python -m fits_processor stack frame_*.fits -o stacked.fits --method median

# PNG thumbnail with asinh stretch (standard in survey astronomy)
python -m fits_processor thumbnail stacked.fits --stretch asinh

# catalog a directory of FITS files → CSV
python -m fits_processor catalog /data/2024-06-15/ --format csv
```

## Notes

- Uses `astropy` for FITS I/O and WCS, `numpy` for image math
- Asinh stretch default follows Lupton et al. 2004 (SDSS standard)
- ZScale interval default matches DS9 behavior
- NaN-safe throughout — bad pixels propagate as NaN, not inf
- Parallel I/O for batch operations via `concurrent.futures`
- Sigma-clipped mean available for aggressive outlier rejection

## Tests

```bash
pytest -v
```

Test fixtures generate synthetic FITS data (star fields, calibration frames) — no real data needed.
