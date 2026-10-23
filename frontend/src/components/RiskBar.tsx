import { RISK_COLORS, RISK_LABELS, RISK_LEVELS } from '../lib/risk'
import type { RouteSummary } from '../types/api'

const MILES_BY_LEVEL = [
  'low_miles',
  'moderate_miles',
  'high_miles',
  'severe_miles',
  'no_travel_miles',
] as const

/** Stacked bar: share of the route's miles at each risk level. */
export function RiskBar({ summary, distance }: { summary: RouteSummary; distance: number }) {
  const parts = RISK_LEVELS.map((level) => ({ level, miles: summary[MILES_BY_LEVEL[level]] }))
  const description = parts
    .filter((p) => p.miles > 0)
    .map((p) => `${RISK_LABELS[p.level]} ${Math.round(p.miles)} mi`)
    .join(', ')
  return (
    <div
      className="flex h-2.5 w-full overflow-hidden rounded-full bg-gray-100"
      role="img"
      aria-label={description}
    >
      {parts.map(
        ({ level, miles }) =>
          miles > 0 && (
            <div
              key={level}
              title={`${RISK_LABELS[level]}: ${Math.round(miles)} mi`}
              style={{ width: `${(miles / distance) * 100}%`, backgroundColor: RISK_COLORS[level] }}
            />
          ),
      )}
    </div>
  )
}
