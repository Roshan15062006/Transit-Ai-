"""
download_images.py
==================
Download Google Street View images for each bus stop in bus_stops.csv.

Part of: Transit Stop Identification (AI/ML Project)

REQUIRED LIBRARIES
------------------
    pip install requests python-dotenv

HOW TO GET A GOOGLE API KEY (free, takes 5 minutes)
----------------------------------------------------
  1. Go to https://console.cloud.google.com
  2. Click "Select a project" → "New Project" → name it anything → Create
  3. In the search bar, type "Street View Static API" → click it → Enable
  4. In the left menu, go to "APIs & Services" → "Credentials"
  5. Click "+ Create Credentials" → "API Key"
  6. Copy the key shown — paste it into your .env file (see below)

HOW TO STORE YOUR API KEY SECURELY (.env file)
-----------------------------------------------
  1. Create a file named exactly:  .env   (in the same folder as this script)
  2. Add this one line inside it:
         GOOGLE_API_KEY=your_actual_key_here
  3. Save the file. That's it — the script reads it automatically.

  IMPORTANT: Never paste your API key directly into the script.
             Never upload your .env file to GitHub (it's in .gitignore).

HOW TO RUN
----------
    # Basic run (downloads first 50 images for Bengaluru stops)
    python download_images.py

    # Custom CSV or limit
    python download_images.py --csv bus_stops.csv --limit 100
    python download_images.py --csv mumbai_bus_stops.csv --limit 50

    # See all options
    python download_images.py --help
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# ──────────────────────────────────────────────────────────────
# CONFIGURATION — tweak these if needed
# ──────────────────────────────────────────────────────────────

DEFAULT_CSV        = "bus_stops.csv"      # input CSV file
DEFAULT_OUTPUT_DIR = "transit_images"     # folder to save images into
DEFAULT_LIMIT      = 50                   # max images to download
REQUEST_DELAY      = 1.0                  # seconds to wait between requests
IMAGE_SIZE         = "640x480"            # width x height (max 640x640 free)
IMAGE_FOV          = 90                   # field of view: 90=normal, 60=zoomed
IMAGE_PITCH        = 0                    # camera tilt: 0=horizontal

# Street View API endpoints
SV_IMAGE_URL    = "https://maps.googleapis.com/maps/api/streetview"
SV_METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"


# ──────────────────────────────────────────────────────────────
# STEP 0 — LOAD API KEY FROM .env FILE
# ──────────────────────────────────────────────────────────────

def load_api_key():
    """
    Load the Google API key from a .env file or environment variable.

    We try two methods in order:
      1. Read the .env file manually (works even without python-dotenv)
      2. Fall back to python-dotenv if installed
      3. Fall back to an environment variable already set in the shell

    This keeps your API key out of the source code entirely.
    """
    # Method 1: Read .env file manually (no library needed)
    env_path = Path(".env")
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key   = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value   # put into environment

    # Method 2: Try python-dotenv (better, handles edge cases)
    else:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass   # fine — we already tried manual parsing above

    # Retrieve the key
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()

    if not api_key:
        print("\nERROR: No API key found.")
        print("─" * 52)
        print("Create a file named '.env' in this folder with:")
        print("    GOOGLE_API_KEY=your_actual_key_here")
        print("\nSee the script header for instructions to get a free key.")
        sys.exit(1)

    return api_key


# ──────────────────────────────────────────────────────────────
# STEP 1 — READ THE CSV FILE
# ──────────────────────────────────────────────────────────────

def read_csv(filepath):
    """
    Read bus stop data from a CSV file.

    Expected columns: id, latitude, longitude
    Extra columns are ignored — so this works with bus_stops.csv
    from our earlier collector script.

    Parameters
    ----------
    filepath : str — path to the CSV file

    Returns
    -------
    list of dicts, each with: id, latitude, longitude
    """
    if not Path(filepath).exists():
        print(f"\nERROR: File not found: '{filepath}'")
        print("Make sure bus_stops.csv is in the same folder as this script.")
        print("Run fetch_bus_stops.py first to generate it.")
        sys.exit(1)

    stops = []
    skipped = 0

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Validate that required columns exist
        required = {"id", "latitude", "longitude"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required - set(reader.fieldnames or [])
            print(f"\nERROR: CSV is missing columns: {missing}")
            print(f"Found columns: {reader.fieldnames}")
            sys.exit(1)

        for row in reader:
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])

                # Validate coordinate ranges
                if not (-90 <= lat <= 90):
                    raise ValueError(f"Invalid latitude: {lat}")
                if not (-180 <= lon <= 180):
                    raise ValueError(f"Invalid longitude: {lon}")

                stops.append({
                    "id":        str(row["id"]).strip(),
                    "latitude":  lat,
                    "longitude": lon,
                })

            except (ValueError, KeyError) as e:
                skipped += 1
                # Don't crash on bad rows — just skip them
                continue

    if skipped:
        print(f"  Warning: Skipped {skipped} rows with invalid coordinates.")

    if not stops:
        print(f"\nERROR: No valid stops found in '{filepath}'.")
        sys.exit(1)

    return stops


# ──────────────────────────────────────────────────────────────
# STEP 2 — CHECK STREET VIEW COVERAGE (FREE API CALL)
# ──────────────────────────────────────────────────────────────

def check_coverage(lat, lon, api_key):
    """
    Check if Street View imagery exists at this location BEFORE downloading.

    This uses the metadata endpoint, which is completely free and does NOT
    count against your image download quota. Always call this first.

    Parameters
    ----------
    lat, lon : float — coordinates to check
    api_key  : str   — your Google API key

    Returns
    -------
    bool : True if coverage exists, False otherwise
    """
    params = {
        "location": f"{lat},{lon}",
        "key":      api_key,
    }
    url = f"{SV_METADATA_URL}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "OK"

    except Exception:
        # If metadata check fails, attempt download anyway
        return True


# ──────────────────────────────────────────────────────────────
# STEP 3 — DOWNLOAD ONE IMAGE
# ──────────────────────────────────────────────────────────────

def download_image(lat, lon, api_key, save_path,
                   size=IMAGE_SIZE, fov=IMAGE_FOV, pitch=IMAGE_PITCH):
    """
    Download a Street View image for a lat/lon coordinate and save it.

    The Street View Static API returns a JPEG image directly — no SDK,
    no complex setup. We just build a URL with parameters and fetch it.

    URL format:
        https://maps.googleapis.com/maps/api/streetview
            ?location=LAT,LON
            &size=640x480
            &fov=90
            &pitch=0
            &key=YOUR_API_KEY

    Parameters
    ----------
    lat, lon  : float — coordinates
    api_key   : str   — Google API key
    save_path : str   — full path to save the JPEG file
    size      : str   — image dimensions e.g. "640x480"
    fov       : int   — field of view (lower = more zoomed)
    pitch     : int   — camera tilt angle

    Returns
    -------
    bool : True if download succeeded, False if it failed
    """
    params = {
        "location": f"{lat},{lon}",
        "size":     size,
        "fov":      fov,
        "pitch":    pitch,
        "key":      api_key,
    }
    url = f"{SV_IMAGE_URL}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            image_data = resp.read()

        # Street View returns a small grey "no imagery" image for missing
        # locations instead of an error. We detect this by checking file size.
        # Real images are typically > 10 KB; placeholder is ~5 KB.
        if len(image_data) < 5000:
            return False

        with open(save_path, "wb") as f:
            f.write(image_data)

        return True

    except urllib.error.HTTPError as e:
        if e.code == 403:
            print("\n  FATAL: API key is invalid or Street View API is not enabled.")
            print("  Check: https://console.cloud.google.com → APIs & Services")
            sys.exit(1)
        return False

    except urllib.error.URLError:
        # Network error — skip this stop
        return False

    except Exception:
        return False


# ──────────────────────────────────────────────────────────────
# STEP 4 — MAIN DOWNLOAD LOOP
# ──────────────────────────────────────────────────────────────

def download_all(stops, api_key, output_dir, limit, delay):
    """
    Loop through bus stops and download a Street View image for each one.

    For each stop we:
      1. Skip if an image was already downloaded (resume support)
      2. Check coverage exists (free metadata call)
      3. Download the image
      4. Wait `delay` seconds before the next request

    Parameters
    ----------
    stops      : list of dicts from read_csv()
    api_key    : str   — Google API key
    output_dir : str   — folder to save images
    limit      : int   — max number of images to download
    delay      : float — seconds between requests

    Returns
    -------
    dict with counts: downloaded, skipped, failed, no_coverage
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Apply limit — take only the first N stops
    stops_to_process = stops[:limit]

    counts = {
        "downloaded":  0,
        "skipped":     0,   # already existed
        "no_coverage": 0,   # no Street View at this location
        "failed":      0,   # network/API error
    }

    total = len(stops_to_process)
    print(f"\n  Downloading up to {total} images → {output_dir}/\n")

    for i, stop in enumerate(stops_to_process, start=1):
        stop_id = stop["id"]
        lat     = stop["latitude"]
        lon     = stop["longitude"]

        # Image filename: use the stop ID so it links back to the CSV
        filename  = f"{stop_id}.jpg"
        save_path = os.path.join(output_dir, filename)

        # Progress prefix shown on every line
        prefix = f"  [{i:>3}/{total}]  id={stop_id}"

        # ── Skip if already downloaded (resume if script was interrupted) ──
        if Path(save_path).exists():
            print(f"{prefix}  SKIP (already exists)")
            counts["skipped"] += 1
            continue

        # ── Check Street View coverage (free call) ──────────────────────
        has_coverage = check_coverage(lat, lon, api_key)
        if not has_coverage:
            print(f"{prefix}  NO COVERAGE")
            counts["no_coverage"] += 1
            time.sleep(delay * 0.5)   # shorter pause for metadata-only calls
            continue

        # ── Download the image ───────────────────────────────────────────
        success = download_image(lat, lon, api_key, save_path)

        if success:
            size_kb = Path(save_path).stat().st_size // 1024
            print(f"{prefix}  OK  ({size_kb} KB)  → {filename}")
            counts["downloaded"] += 1
        else:
            print(f"{prefix}  FAILED (no imagery or network error)")
            counts["failed"] += 1

        # ── Wait before next request ─────────────────────────────────────
        # This is important — hammering the API can get your key blocked
        time.sleep(delay)

    return counts


# ──────────────────────────────────────────────────────────────
# SUMMARY REPORT
# ──────────────────────────────────────────────────────────────

def print_report(counts, output_dir, csv_path):
    """Print a clean summary after the download loop finishes."""
    total_attempted = sum(counts.values())
    divider = "─" * 52

    print(f"\n{divider}")
    print("  Download complete — Summary")
    print(divider)
    print(f"  Downloaded   : {counts['downloaded']} images")
    print(f"  Already had  : {counts['skipped']} images")
    print(f"  No coverage  : {counts['no_coverage']} locations")
    print(f"  Failed       : {counts['failed']} requests")
    print(divider)
    print(f"  Images saved : {output_dir}/")
    print(f"  Source CSV   : {csv_path}")
    print(divider + "\n")

    if counts["downloaded"] == 0 and counts["skipped"] == 0:
        print("  No images were saved.")
        print("  Check that your API key is valid and")
        print("  Street View Static API is enabled.\n")


# ──────────────────────────────────────────────────────────────
# COMMAND-LINE INTERFACE
# ──────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download Street View images for bus stops from a CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_images.py
  python download_images.py --limit 100
  python download_images.py --csv mumbai_bus_stops.csv --limit 50
  python download_images.py --output my_images/ --delay 1.5
        """,
    )
    parser.add_argument("--csv",    default=DEFAULT_CSV,
                        help=f"Input CSV file (default: {DEFAULT_CSV})")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR,
                        help=f"Output image folder (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--limit",  default=DEFAULT_LIMIT, type=int,
                        help=f"Max images to download (default: {DEFAULT_LIMIT})")
    parser.add_argument("--delay",  default=REQUEST_DELAY, type=float,
                        help=f"Seconds between requests (default: {REQUEST_DELAY})")
    return parser.parse_args()


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    print("\n" + "=" * 52)
    print("  Transit Stop Identification — Image Downloader")
    print("=" * 52)
    print(f"  CSV file  : {args.csv}")
    print(f"  Output    : {args.output}/")
    print(f"  Limit     : {args.limit} images")
    print(f"  Delay     : {args.delay}s between requests")
    print()

    # Step 0: Load API key from .env
    print("[0/4] Loading API key from .env ...")
    api_key = load_api_key()
    print(f"  API key loaded (ends in ...{api_key[-4:]})\n")

    # Step 1: Read CSV
    print(f"[1/4] Reading {args.csv} ...")
    stops = read_csv(args.csv)
    print(f"  Found {len(stops)} valid stops in CSV.\n")

    # Step 2 + 3: Check coverage and download images
    print("[2/4] Checking coverage + downloading images ...")
    counts = download_all(
        stops      = stops,
        api_key    = api_key,
        output_dir = args.output,
        limit      = args.limit,
        delay      = args.delay,
    )

    # Step 4: Report
    print("[4/4] Done.")
    print_report(counts, args.output, args.csv)


if __name__ == "__main__":
    main()
