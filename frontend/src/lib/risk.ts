import type { ExpressionSpecification } from 'maplibre-gl'

import type { RiskLevel } from '../types/api'

export const RISK_LEVELS: RiskLevel[] = [0, 1, 2, 3, 4]

export const RISK_LABELS: Record<RiskLevel, string> = {
  0: 'Low',
  1: 'Moderate',
  2: 'High',
  3: 'Severe',
  4: 'No Travel',
}

// Ordered from light to dark as well as by hue, so the levels stay distinguishable with
// red-green colour blindness and in greyscale.
export const RISK_COLORS: Record<RiskLevel, string> = {
  0: '#1a9850',
  1: '#f6d743',
  2: '#f28e2b',
  3: '#d62728',
  4: '#3b0f4f',
}

/** MapLibre `match` expression mapping a numeric `level` property to its colour. */
export const RISK_COLOR_EXPRESSION: ExpressionSpecification = [
  'match',
  ['get', 'level'],
  0,
  RISK_COLORS[0],
  1,
  RISK_COLORS[1],
  2,
  RISK_COLORS[2],
  3,
  RISK_COLORS[3],
  4,
  RISK_COLORS[4],
  '#888888',
]
