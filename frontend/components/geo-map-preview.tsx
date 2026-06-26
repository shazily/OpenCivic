"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GeoColumnPair } from "@/lib/geo/detect-geo";
import { rowsToGeoJson } from "@/lib/geo/detect-geo";

interface GeoMapPreviewProps {
  rows: Record<string, unknown>[];
  geoColumns: GeoColumnPair;
}

export function GeoMapPreview({ rows, geoColumns }: GeoMapPreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const geojson = rowsToGeoJson(rows, geoColumns);
    if (geojson.features.length === 0) {
      return;
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: geojson.features[0].geometry.coordinates as [number, number],
      zoom: 4,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.on("load", () => {
      map.addSource("dataset-points", {
        type: "geojson",
        data: geojson,
      });
      map.addLayer({
        id: "dataset-points-layer",
        type: "circle",
        source: "dataset-points",
        paint: {
          "circle-radius": 5,
          "circle-color": "#1d4ed8",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#fff",
        },
      });

      const bounds = new maplibregl.LngLatBounds();
      for (const feature of geojson.features) {
        if (feature.geometry.type === "Point") {
          bounds.extend(feature.geometry.coordinates as [number, number]);
        }
      }
      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 40, maxZoom: 12 });
      }
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [rows, geoColumns]);

  const pointCount = rowsToGeoJson(rows, geoColumns).features.length;

  if (pointCount === 0) {
    return null;
  }

  return (
    <Card className="mb-8">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Map preview</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-[var(--color-foreground-secondary)]">
          {pointCount.toLocaleString()} point{pointCount === 1 ? "" : "s"} from{" "}
          <code className="text-xs">{geoColumns.lat}</code> /{" "}
          <code className="text-xs">{geoColumns.lon}</code>
        </p>
        <div
          ref={containerRef}
          className="h-72 w-full overflow-hidden rounded-lg border border-[var(--color-border)]"
          role="img"
          aria-label="GeoJSON map preview"
        />
      </CardContent>
    </Card>
  );
}
