# Transit Stop Identification

A beginner-friendly computer vision project that identifies transit stops (bus stops, tram stops, etc.) from street-level images using OpenStreetMap data and deep learning.

> **GSoC Project in Progress** — Building toward a full transit stop identification system using YOLOv8 object detection + MobileNetV2 classification + OCR.

---

## Project Overview

```
Phase 1 (Current) → Fetch stop locations from OpenStreetMap → Save to CSV → Download Street View images
Phase 2           → Label images → Train YOLOv8 object detector
Phase 3           → Add OCR to read stop names → Match to OSM database
Phase 4           → Deploy as REST API + mobile-friendly web app
```

---

## Repository Structure

```
transit-stop-identification/
│
├── transit_stop_collector.py   # Step 1: Fetch bus stop locations from OSM
├── bus_stops.csv               # Sample output CSV (Bengaluru stops)
│
├── requirements.txt            # Python dependencies
├── .gitignore                  # Files to exclude from git
├── LICENSE                     # MIT License
└── README.md                   # This file
```

---

## Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/transit-stop-identification.git
cd transit-stop-identification
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# Activate:
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the collector

```bash
# Test with built-in sample data (no internet needed)
python transit_stop_collector.py --demo

# Fetch real stops for Bengaluru
python transit_stop_collector.py

# Different city
python transit_stop_collector.py --city mumbai
python transit_stop_collector.py --city delhi
python transit_stop_collector.py --city london

# Fetch more stops
python transit_stop_collector.py --city bengaluru --max 1000

# Also download Street View images
python transit_stop_collector.py --streetview YOUR_GOOGLE_API_KEY
```

---

## Output

Running the script produces a CSV with these columns:

| Column | Description |
|--------|-------------|
| `id` | OpenStreetMap node ID |
| `lat` | Latitude (decimal degrees) |
| `lon` | Longitude (decimal degrees) |
| `name` | Stop name (from OSM tags) |
| `operator` | Transit operator (e.g. BMTC, DTC) |
| `routes` | Route numbers serving this stop |
| `streetview_url` | Clickable Google Street View link |

Sample output (`bus_stops.csv`):

```
id,lat,lon,name,operator,routes,streetview_url
1001,12.9716,77.5946,Majestic Bus Stand,BMTC,"1,2,5,10",https://...
1002,12.9784,77.6408,Indiranagar 100ft Rd,BMTC,"300G,314",https://...
```

---

## Supported Cities

| City | Flag |
|------|------|
| Bengaluru | `--city bengaluru` |
| Mumbai | `--city mumbai` |
| Delhi | `--city delhi` |
| Chennai | `--city chennai` |
| Hyderabad | `--city hyderabad` |
| London | `--city london` |
| New York | `--city newyork` |

To add a custom city, find the bounding box at [bboxfinder.com](http://bboxfinder.com) and edit the `CITY_BBOXES` dictionary in the script.

---

## Street View Image Download (Optional)

### Get a Google API key (free tier: ~100 images/month free)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project → Enable **Street View Static API**
3. Credentials → **Create API Key**

```bash
python transit_stop_collector.py --streetview YOUR_API_KEY
```

Images are saved to `streetview_images/` named by OSM node ID. The script checks metadata first (free call) before downloading, so quota is only spent where coverage exists.

---

## How It Works

### OpenStreetMap Query (Overpass API)

```
node["highway"="bus_stop"](south,west,north,east);
node["public_transport"="stop_position"](south,west,north,east);
```

Both tag variants are queried since OSM mappers use different conventions for bus stops.

### Street View API flow

1. Free metadata call → confirm coverage exists at lat/lon
2. Download image only if status is `OK`
3. Save as `{osm_node_id}.jpg` for cross-referencing with CSV

---

## Roadmap

- [x] Phase 1 — Data collection: OSM locations + Street View images
- [ ] Phase 2 — YOLOv8 object detection (detect signs in images)
- [ ] Phase 3 — EasyOCR pipeline (read stop name text)
- [ ] Phase 4 — Stop identity matching (OSM / GTFS database)
- [ ] Phase 5 — FastAPI REST endpoint + web UI
- [ ] Phase 6 — TFLite export for Android / iOS

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Data source | OpenStreetMap via Overpass API |
| Image source | Google Street View Static API |
| Classification | MobileNetV2 (TensorFlow / Keras) |
| Detection model | YOLOv8 (Ultralytics) — Phase 2 |
| OCR | EasyOCR — Phase 3 |
| Backend API | FastAPI — Phase 4 |
| Mobile export | TFLite — Phase 5 |

---

## Contributing

Contributions welcome — especially:
- City bounding box presets
- OCR support for non-Latin scripts (Hindi, Tamil, Kannada)
- Labelled image datasets from your city

Open an issue before submitting a large PR.

---

## License

MIT License — see [LICENSE](LICENSE).

Map data © OpenStreetMap contributors, [ODbL licence](https://www.openstreetmap.org/copyright).
