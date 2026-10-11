# sutd-stat

Singapore PM2.5 × regional fires × local weather — data crawl & data dictionary.

**Project question:** Do satellite fire detections and local meteorological conditions improve short-horizon prediction of high-PM2.5 periods in Singapore beyond persistence and seasonality?

## Data sources

- **NEA PM2.5** — `data.gov.sg` real-time API (`/v2/real-time/api/pm25`), hourly readings per region.
- **NEA weather** (collection 1459) — `data.gov.sg` real-time API, 1-minute station readings for temperature, wind, rainfall, etc.
- **NASA FIRMS active fires** — satellite fire detections (MODIS/VIIRS) via the FIRMS area CSV API, for Singapore's surrounding region.

## Setup

1. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in your keys:
   ```
   FIRMS_MAP_KEY=your_firms_map_key   # https://firms.modaps.eosdis.nasa.gov/api/map_key/
   ```
   `DATAGOV_API_KEY` is optional and only raises the data.gov.sg anonymous rate limit.
3. Open `data.ipynb` and run the cells top to bottom.

### Running on Google Colab

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/huythanh1324/sutd-stat/blob/main/data.ipynb)

1. Open the notebook with the badge above, then **File → Save a copy in Drive** so your edits persist.
2. Add `FIRMS_MAP_KEY` (and optionally `DATAGOV_API_KEY`) under **Secrets** (key icon in the left sidebar) and enable notebook access.
3. Run all cells. The setup cell mounts Google Drive and caches raw data in `MyDrive/claude-projects/sutd-stat/data/raw/`. Upload an existing local `data/raw/` folder there to skip the slow weather crawl.

## Project structure

```
data.ipynb         # data crawl, data dictionary, profiling, and caveats for each source
data/raw/          # cached raw CSVs pulled by the notebook (gitignored)
requirements.txt   # Python dependencies
.env.example       # template for required API keys
```

## Notebook contents

1. Setup & configuration
2. NEA PM2.5
3. NEA weather (collection 1459)
4. NASA FIRMS active fires
5. Time alignment notes for joining the tables
6. Caveats to carry into modelling
