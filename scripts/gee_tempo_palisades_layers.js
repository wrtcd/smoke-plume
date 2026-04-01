/**
 * Google Earth Engine — TEMPO NO2 L3 (QA-filtered) over Palisades / LA
 *
 * Open: https://code.earthengine.google.com/
 * Paste this script → Run.
 *
 * Collection: NASA/TEMPO/NO2_L3_QA
 * See: https://developers.google.com/earth-engine/datasets/catalog/NASA_TEMPO_NO2_L3_QA
 *
 * Note: L3 is gridded (~2.2 km); not identical to your L2 NetCDF swath.
 */

// --- Broader SoCal: Ventura / LA basin / Orange / western Inland Empire (adjust as needed)
// Rectangle: [minLon, minLat, maxLon, maxLat] in WGS84
var PALISADES_AOI = ee.Geometry.Rectangle({
  coords: [-119.15, 33.55, -117.45, 34.65],
  geodesic: false
});

// Single day (UTC) — Palisades fire window Jan 2025
var DATE_START = '2025-01-10';
var DATE_END = '2025-01-11';

// --- Collection
var col = ee.ImageCollection('NASA/TEMPO/NO2_L3_QA')
  .filterBounds(PALISADES_AOI)
  .filterDate(DATE_START, DATE_END);

// One composite for the day (mean of all L3 snapshots touching the AOI).
// For a single overpass character, try .mosaic() or inspect ImageCollection size and .sort('system:time_start').first().
var no2Mean = col.select('vertical_column_troposphere').mean().clip(PALISADES_AOI);
var no2Unc = col.select('vertical_column_troposphere_uncertainty').mean().clip(PALISADES_AOI);
var cloud = col.select('eff_cloud_fraction').mean().clip(PALISADES_AOI);
var weight = col.select('weight').mean().clip(PALISADES_AOI);

// Tropospheric NO2 column (molecules/cm^2) — same scale as Earthdata browse images
var visNo2 = {
  min: 0,
  max: 3e16,
  bands: ['vertical_column_troposphere'],
  palette: [
    '000080', '0000D9', '4000FF', '8000FF', '0080FF',
    '00D9FF', '80FFFF', 'FF8080', 'D90000', '800000'
  ]
};

var visCloud = { min: 0, max: 1, palette: ['1a9850', 'fee08b', 'd73027'] };
var visWeight = { min: 0, max: 1e7, palette: ['black', 'yellow', 'white'] };

Map.centerObject(PALISADES_AOI, 10);
Map.addLayer(PALISADES_AOI, { color: 'white' }, 'AOI outline', true, 0.4);

Map.addLayer(no2Mean, visNo2, 'NO2 troposphere (mean, Jan 10 2025)', true, 0.85);
Map.addLayer(no2Unc, { min: 0, max: 1e16, palette: ['fff7ec', 'fee8c8', 'fdbb84', 'e34a33'] },
  'NO2 trop. uncertainty (mean)', false, 0.75);
Map.addLayer(cloud, visCloud, 'Effective cloud fraction (mean)', false, 0.7);
Map.addLayer(weight, visWeight, 'L3 weight (L2 overlap area sum)', false, 0.6);

// Optional: unfiltered sibling collection for comparison (more gaps / clouds)
// var colRaw = ee.ImageCollection('NASA/TEMPO/NO2_L3')
//   .filterBounds(PALISADES_AOI).filterDate(DATE_START, DATE_END);
// Map.addLayer(colRaw.select('vertical_column_troposphere').mean().clip(PALISADES_AOI),
//   visNo2, 'NO2 (NO2_L3, not QA-filtered)', false);

// Console summary (human-readable times in UTC)
print('Images in filter:', col.size());
var tMinMs = col.aggregate_min('system:time_start');
var tMaxMs = col.aggregate_max('system:time_start');
print('Time range (UTC):', ee.Date(tMinMs).format('YYYY-MM-dd HH:mm:ss'), '→', ee.Date(tMaxMs).format('YYYY-MM-dd HH:mm:ss'));
print('Time range (epoch ms, for debugging):', tMinMs, tMaxMs);
