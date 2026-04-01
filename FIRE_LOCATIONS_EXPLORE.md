# California wildfires — exploration list (Cal Fire–based)

**Purpose:** Rough **axis-aligned bounding boxes** (NW / SE corners in **WGS84**, decimal degrees) to search Planet / TEMPO / other data. **Not** official GIS perimeters.

**Important**

- **Acres** and **dates** are from **public Cal Fire incident pages** or widely cited post-season totals; small differences can exist across sources.
- **Bounding boxes** are **hand-drawn envelopes** around the general burned area for AOI search — **wider than the true fire polygon**. For analysis, download **official perimeter** (GeoJSON/SHP) from [Cal Fire](https://www.fire.ca.gov/resources/disaster-recovery/geographic-information-systems-and-maps) or [FRAP / data.ca.gov](https://data.ca.gov/).
- **NW corner** = **north** + **west** (max latitude, most negative longitude). **SE corner** = **south** + **east** (min latitude, least negative longitude).

---

## Top 10 (by approximate final acreage, large perimeters first)

| # | Incident | Start date (approx.) | Area burned (approx.) | Counties / region |
|---|----------|----------------------|------------------------|-------------------|
| 1 | [Park Fire](https://www.fire.ca.gov/incidents/2024/7/24/park-fire) | 2024-07-24 | ~429,600 ac | Butte, Tehama, Plumas, Shasta |
| 2 | [Gifford Fire](https://www.fire.ca.gov/incidents/2025/8/1/gifford-fire) | 2025-08-01 | ~131,600 ac | San Luis Obispo, Santa Barbara |
| 3 | [Madre Fire](https://www.fire.ca.gov/incidents/2025/7/2/madre-fire) | 2025-07-02 | ~80,800 ac | San Luis Obispo (Highway 166 / Cuyama) |
| 4 | [Borel Fire](https://www.fire.ca.gov/incidents/2024/7/24/borel-fire) | 2024-07-24 | ~59,300 ac | Kern (Lake Isabella / Kern River area) |
| 5 | [Bridge Fire](https://www.fire.ca.gov/incidents/2024/9/8/bridge-fire) | 2024-09-08 | ~56,000 ac | Los Angeles, San Bernardino (San Gabriels) |
| 6 | [Line Fire](https://www.fire.ca.gov/incidents/2024/9/5/line-fire) | 2024-09-05 | ~44,000 ac | San Bernardino (Highland / foothills) |
| 7 | [Garnet Fire](https://www.fire.ca.gov/incidents/2025/8/24/garnet-fire) | 2025-08-24 | ~28,800 ac | Fresno (Sierra NF) |
| 8 | [Palisades Fire](https://www.fire.ca.gov/incidents/2025/1/7/palisades-fire/) | 2025-01-07 | ~23,400 ac | Los Angeles (Santa Monica Mtns / Malibu) |
| 9 | [Airport Fire](https://www.fire.ca.gov/incidents/2024/9/9/airport-fire) | 2024-09-09 | ~23,500 ac | Orange, Riverside (Cleveland NF) |
| 10 | [Eaton Fire](https://www.fire.ca.gov/incidents/2025/1/7/eaton-fire/) | 2025-01-07 | ~14,000 ac | Los Angeles (Altadena / Pasadena) |

---

## Bounding boxes (WGS84)

Values are **approximate**; pad outward if your tool clips to the box edge.

### 1. Park Fire (2024)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 40.55 | 122.15 |
| **SE** | 39.55 | 121.20 |

### 2. Gifford Fire (2025)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 35.55 | 120.55 |
| **SE** | 34.75 | 119.65 |

### 3. Madre Fire (2025)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 35.25 | 120.25 |
| **SE** | 34.85 | 119.45 |

### 4. Borel Fire (2024)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 35.85 | 118.95 |
| **SE** | 35.35 | 118.25 |

### 5. Bridge Fire (2024)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 34.38 | 117.95 |
| **SE** | 34.15 | 117.55 |

### 6. Line Fire (2024)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 34.32 | 117.35 |
| **SE** | 34.08 | 117.05 |

### 7. Garnet Fire (2025)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 37.55 | 119.45 |
| **SE** | 37.10 | 118.85 |

### 8. Palisades Fire (2025)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 34.14 | 118.78 |
| **SE** | 34.00 | 118.45 |

### 9. Airport Fire (2024)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 33.78 | 117.62 |
| **SE** | 33.62 | 117.42 |

### 10. Eaton Fire (2025)

| Corner | Latitude °N | Longitude °W |
|--------|----------------|---------------|
| **NW** | 34.26 | 118.20 |
| **SE** | 34.16 | 118.04 |

---

## Quick copy (min/max for filters)

Many tools want **min latitude, max latitude, min longitude, max longitude** (all in °N and °W as positive west stored negative):

| # | Incident | lat min (S) | lat max (N) | lon min (W, −) | lon max (E, −) |
|---|----------|---------------|-------------|----------------|----------------|
| 1 | Park | 39.55 | 40.55 | −122.15 | −121.20 |
| 2 | Gifford | 34.75 | 35.55 | −120.55 | −119.65 |
| 3 | Madre | 34.85 | 35.25 | −120.25 | −119.45 |
| 4 | Borel | 35.35 | 35.85 | −118.95 | −118.25 |
| 5 | Bridge | 34.15 | 34.38 | −117.95 | −117.55 |
| 6 | Line | 34.08 | 34.32 | −117.35 | −117.05 |
| 7 | Garnet | 37.10 | 37.55 | −119.45 | −118.85 |
| 8 | Palisades | 34.00 | 34.14 | −118.78 | −118.45 |
| 9 | Airport | 33.62 | 33.78 | −117.62 | −117.42 |
| 10 | Eaton | 34.16 | 34.26 | −118.20 | −118.04 |

---

*Generated for smoke-plume project exploration. Refine boxes against official perimeter before publishing maps or statistics.*
