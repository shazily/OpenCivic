/** Detect latitude/longitude column pairs in tabular schema. */

const LAT_NAMES = new Set(["latitude", "lat", "y", "latitud"]);
const LON_NAMES = new Set(["longitude", "lon", "lng", "long", "x", "longitud"]);

export interface GeoColumnPair {
  lat: string;
  lon: string;
}

export function detectGeoColumns(columnNames: string[]): GeoColumnPair | null {
  let latCol: string | null = null;
  let lonCol: string | null = null;

  for (const name of columnNames) {
    const key = name.toLowerCase().trim();
    if (LAT_NAMES.has(key)) {
      latCol = name;
    }
    if (LON_NAMES.has(key)) {
      lonCol = name;
    }
  }

  if (latCol && lonCol) {
    return { lat: latCol, lon: lonCol };
  }
  return null;
}

export function rowsToGeoJson(
  rows: Record<string, unknown>[],
  pair: GeoColumnPair,
  limit = 500,
): { type: "FeatureCollection"; features: Array<{ type: "Feature"; geometry: { type: "Point"; coordinates: [number, number] }; properties: Record<string, unknown> }> } {
  const features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: Record<string, unknown>;
  }> = [];

  for (const row of rows.slice(0, limit)) {
    const lat = Number(row[pair.lat]);
    const lon = Number(row[pair.lon]);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      continue;
    }
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      continue;
    }
    features.push({
      type: "Feature",
      geometry: { type: "Point", coordinates: [lon, lat] },
      properties: Object.fromEntries(
        Object.entries(row).filter(([key]) => key !== pair.lat && key !== pair.lon),
      ),
    });
  }

  return { type: "FeatureCollection", features };
}
