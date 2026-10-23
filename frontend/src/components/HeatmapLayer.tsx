import type { HeatmapLayerSpecification } from 'maplibre-gl'
import { useEffect, useMemo } from 'react'
import { Layer, Source, useMap } from 'react-map-gl/maplibre'

import { HEATMAP_COLOR, heatmapFeatures, kernelSettings, weightExpression } from '../lib/heatmap'
import type { Heatmap, HeatmapMetric } from '../types/api'

const LAYER_ID = 'weather-heatmap'

interface Props {
  heatmap: Heatmap
  hour: number
  metric: HeatmapMetric
  visible: boolean
  beforeId?: string
}

/** Smooth scrubbing: the GeoJSON source is created once per heatmap response; moving the
 * slider only swaps the `heatmap-weight` expression via setPaintProperty, at most once per
 * animation frame. No network requests and no source re-uploads while scrubbing. */
export function HeatmapLayer({ heatmap, hour, metric, visible, beforeId }: Props) {
  const { current: mapRef } = useMap()
  const data = useMemo(() => heatmapFeatures(heatmap), [heatmap])

  // Paint as of the first render only: later hour/metric changes go through the effect
  // below, so React never diffs or re-sets them.
  const paint = useMemo<HeatmapLayerSpecification['paint']>(() => {
    const { radius, intensity } = kernelSettings(heatmap)
    return {
      'heatmap-weight': weightExpression('risk', 0),
      'heatmap-radius': radius,
      'heatmap-intensity': intensity,
      'heatmap-color': HEATMAP_COLOR,
      // The kernel is ground-sized, so very close zooms would mean screen-filling quads;
      // the corridor view lives at regional zooms anyway.
      'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 8, 0.6, 10, 0],
    }
  }, [heatmap])

  useEffect(() => {
    const map = mapRef?.getMap()
    if (!map) return
    const frame = requestAnimationFrame(() => {
      if (map.getLayer(LAYER_ID)) {
        map.setPaintProperty(LAYER_ID, 'heatmap-weight', weightExpression(metric, hour))
      }
    })
    return () => cancelAnimationFrame(frame)
  }, [mapRef, hour, metric])

  const layout = useMemo(
    () => ({ visibility: visible ? ('visible' as const) : ('none' as const) }),
    [visible],
  )

  return (
    <Source id="weather-heatmap" type="geojson" data={data}>
      <Layer
        id={LAYER_ID}
        type="heatmap"
        maxzoom={10}
        paint={paint}
        layout={layout}
        beforeId={beforeId}
      />
    </Source>
  )
}
