import type { ExpressionSpecification } from 'maplibre-gl'
import type { FeatureCollection, Point } from 'geojson'

import type { Heatmap, HeatmapMetric } from '../types/api'
import { RISK_COLORS } from './risk'

export const HEATMAP_HOURS = 49

/** Per-metric property prefix on each feature: r0..r48, w0.., p0.., s0.. */
const PREFIX: Record<HeatmapMetric, string> = { risk: 'r', wind: 'w', rain: 'p', snow: 's' }

/** Built once per heatmap response. Every hour of every metric is a feature property, so
 * scrubbing only has to change which property the paint expression reads. */
export function heatmapFeatures(heatmap: Heatmap): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: heatmap.points.map((coordinates, i) => {
      const properties: Record<string, number> = {}
      for (let h = 0; h < heatmap.hours.length; h++) {
        properties[`r${h}`] = heatmap.risk[i][h]
        properties[`w${h}`] = heatmap.wind[i][h]
        properties[`p${h}`] = heatmap.rain[i][h]
        properties[`s${h}`] = heatmap.snow[i][h]
      }
      return { type: 'Feature', geometry: { type: 'Point', coordinates }, properties }
    }),
  }
}

/*
 * Making colour mean "risk level" rather than "point density":
 * MapLibre sums a Gaussian per point (sigma = radius / 3, peak 0.3989 * weight * intensity).
 * On a uniform lattice the sum is ~weight * intensity * 2.5066 * sigma^2 / (cell area), with
 * ripple below 0.2% once sigma >= 0.55 spacing. A wider kernel would smooth no further but
 * would spill well outside the corridor (only 2-3 cells wide) and under-read inside it, so
 * sigma is kept at 0.55 spacing and the intensity chosen so the rendered density ~= weight.
 * Each level is then encoded as a fixed weight (Low 0.1 ... No Travel 0.9) and the colour
 * ramp places the level's colour at that density. The radius grows 2x per zoom level so the
 * kernel stays the same size on the ground at every zoom.
 */
const GAUSS_SUM_FACTOR = 2.5066 // 0.3989 * 2 * pi
const SIGMA_PER_SPACING = 0.55

// Band edges of each raw metric (same thresholds as the backend risk table) mapped to the
// density boundaries between colours, so e.g. 30 mph wind renders Moderate yellow.
const METRIC_STOPS: Record<Exclude<HeatmapMetric, 'risk'>, number[]> = {
  wind: [0, 0.08, 25, 0.2, 35, 0.4, 45, 0.6, 55, 0.8, 70, 1],
  rain: [0, 0.08, 0.1, 0.2, 0.25, 0.4, 0.5, 0.6, 1.0, 0.8, 1.5, 1],
  snow: [0, 0.08, 0.5, 0.2, 1, 0.4, 2, 0.6, 3, 0.8, 4, 1],
}

export const METRIC_CAPTIONS: Record<HeatmapMetric, string> = {
  risk: 'Overall risk incl. load rules',
  wind: 'Sustained wind · bands 25 / 35 / 45 / 55 mph',
  rain: 'Rain · bands 0.10 / 0.25 / 0.50 / 1.00 in/hr',
  snow: 'Snow · bands 0.5 / 1 / 2 / 3 in/hr',
}

export function weightExpression(metric: HeatmapMetric, hour: number): ExpressionSpecification {
  const value: ExpressionSpecification = ['get', `${PREFIX[metric]}${hour}`]
  if (metric === 'risk') {
    // -1 = no model data: effectively invisible.
    return ['case', ['<', value, 0], 0.001, ['+', 0.1, ['*', 0.2, value]]]
  }
  return ['interpolate', ['linear'], value, ...METRIC_STOPS[metric]] as ExpressionSpecification
}

export const HEATMAP_COLOR: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['heatmap-density'],
  0,
  'rgba(26,152,80,0)',
  0.04,
  'rgba(26,152,80,0)',
  0.1,
  RISK_COLORS[0],
  0.3,
  RISK_COLORS[1],
  0.5,
  RISK_COLORS[2],
  0.7,
  RISK_COLORS[3],
  0.9,
  RISK_COLORS[4],
]

export function kernelSettings(heatmap: Heatmap) {
  const meanLat = heatmap.points.reduce((sum, [, lat]) => sum + lat, 0) / heatmap.points.length
  const secLat = 1 / Math.cos((meanLat * Math.PI) / 180)
  // Lattice spacing in screen px at zoom 0 along latitude (the larger of the two spacings):
  // world width is 512 px at zoom 0, and Mercator stretches latitude by sec(lat).
  const spacingAtZoom0 = ((heatmap.cell_deg * 512) / 360) * secLat
  const radiusAtZoom0 = 3 * SIGMA_PER_SPACING * spacingAtZoom0 // radius = 3 sigma
  const radius: ExpressionSpecification = [
    'interpolate',
    ['exponential', 2],
    ['zoom'],
    0,
    radiusAtZoom0,
    22,
    radiusAtZoom0 * 2 ** 22,
  ]
  // Lattice cells are square in degrees, so on screen the longitude spacing is the latitude
  // spacing / sec(lat); cell area in px = spacing^2 / sec(lat).
  const intensity = 1 / (GAUSS_SUM_FACTOR * SIGMA_PER_SPACING ** 2 * secLat)
  return { radius, intensity }
}
