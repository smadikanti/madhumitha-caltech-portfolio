#!/usr/bin/env bash
# ============================================================================
# Example: full observation reduction workflow
#
# Demonstrates the typical sequence an astronomer follows after a night
# of observing — inspect raw data, reduce it, stack the exposures,
# generate a thumbnail, and catalog the results.
#
# Usage:
#   chmod +x examples/process_observation.sh
#   ./examples/process_observation.sh /path/to/raw_data/
# ============================================================================

set -euo pipefail

RAW_DIR="${1:?Usage: $0 <raw_data_directory>}"
OUTPUT_DIR="${RAW_DIR}/reduced"

mkdir -p "$OUTPUT_DIR"

echo "=== Step 1: Catalog raw data ==="
python -m fits_processor catalog "$RAW_DIR" \
    --format csv \
    -o "$OUTPUT_DIR/raw_catalog.csv" \
    -v

echo ""
echo "=== Step 2: Inspect a science frame ==="
SCIENCE_FRAME=$(find "$RAW_DIR" -name "*.fits" -type f | head -1)
if [ -z "$SCIENCE_FRAME" ]; then
    echo "No FITS files found in $RAW_DIR"
    exit 1
fi
python -m fits_processor inspect "$SCIENCE_FRAME" -v

echo ""
echo "=== Step 3: Reduce science frame (bias + dark + flat correction) ==="
# In practice you would point these at your actual calibration masters.
# This example shows the command structure.
if [ -f "$RAW_DIR/master_bias.fits" ] && \
   [ -f "$RAW_DIR/master_dark.fits" ] && \
   [ -f "$RAW_DIR/master_flat.fits" ]; then
    python -m fits_processor normalize "$SCIENCE_FRAME" \
        --bias "$RAW_DIR/master_bias.fits" \
        --dark "$RAW_DIR/master_dark.fits" \
        --flat "$RAW_DIR/master_flat.fits" \
        -o "$OUTPUT_DIR/reduced_science.fits" \
        -v
else
    echo "  (Skipping — calibration masters not found. Run without correction.)"
    python -m fits_processor normalize "$SCIENCE_FRAME" \
        -o "$OUTPUT_DIR/reduced_science.fits" \
        -v
fi

echo ""
echo "=== Step 4: Stack multiple exposures ==="
FRAME_COUNT=$(find "$RAW_DIR" -name "*.fits" -type f | wc -l | tr -d ' ')
if [ "$FRAME_COUNT" -ge 2 ]; then
    python -m fits_processor stack "$RAW_DIR"/*.fits \
        -o "$OUTPUT_DIR/stacked.fits" \
        --method median \
        -v
else
    echo "  (Skipping — need at least 2 frames to stack)"
fi

echo ""
echo "=== Step 5: Generate thumbnail ==="
TARGET="$OUTPUT_DIR/stacked.fits"
if [ ! -f "$TARGET" ]; then
    TARGET="$OUTPUT_DIR/reduced_science.fits"
fi
python -m fits_processor thumbnail "$TARGET" \
    --stretch asinh \
    --interval zscale \
    --cmap gray \
    -o "$OUTPUT_DIR/preview.png" \
    -v

echo ""
echo "=== Step 6: Final catalog of reduced data ==="
python -m fits_processor catalog "$OUTPUT_DIR" \
    --format json \
    -o "$OUTPUT_DIR/reduced_catalog.json" \
    -v

echo ""
echo "Done. Results in: $OUTPUT_DIR"
