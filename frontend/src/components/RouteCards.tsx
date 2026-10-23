import { formatDuration, formatMiles, formatTime } from '../lib/format'
import { RISK_COLORS, RISK_LABELS } from '../lib/risk'
import type { Analysis, Route } from '../types/api'
import { RiskBar } from './RiskBar'

interface Props {
  analysis: Analysis
  selectedId: string
  onSelect: (routeId: string) => void
}

/** Cards in ranked order, so the recommended route and its reason come first. */
export function RouteCards({ analysis, selectedId, onSelect }: Props) {
  const byId = new Map(analysis.routes.map((route) => [route.id, route]))
  const ranked = analysis.ranking.map((id) => byId.get(id)).filter((r): r is Route => Boolean(r))
  return (
    <ul className="space-y-2">
      {ranked.map((route) => (
        <li key={route.id}>
          <RouteCard
            route={route}
            recommended={route.id === analysis.recommended_route_id}
            reason={
              route.id === analysis.recommended_route_id ? analysis.recommendation_reason : null
            }
            selected={route.id === selectedId}
            onSelect={() => onSelect(route.id)}
          />
        </li>
      ))}
    </ul>
  )
}

interface CardProps {
  route: Route
  recommended: boolean
  reason: string | null
  selected: boolean
  onSelect: () => void
}

function RouteCard({ route, recommended, reason, selected, onSelect }: CardProps) {
  const { summary } = route
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`w-full rounded-lg border bg-white p-3 text-left transition ${
        selected ? 'border-sky-500 ring-2 ring-sky-200' : 'border-gray-200 hover:border-gray-300'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="font-semibold text-gray-900">{route.name}</span>
        {recommended && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">
            Recommended
          </span>
        )}
        {route.synthesized && (
          <span
            className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600"
            title="Generated through a via waypoint because the routing provider returned fewer than 3 alternatives"
          >
            via waypoint
          </span>
        )}
        <span className="ml-auto flex items-center gap-1 text-xs text-gray-600">
          <span
            className="size-2.5 rounded-full"
            style={{ backgroundColor: RISK_COLORS[summary.max_level] }}
          />
          max {RISK_LABELS[summary.max_level]}
        </span>
      </div>

      <div className="mt-1 text-sm text-gray-700">
        {formatMiles(route.distance_mi)} · {formatDuration(route.duration_s)} · arrives{' '}
        {formatTime(route.arrival_time)}
      </div>

      <div className="mt-2">
        <RiskBar summary={summary} distance={route.distance_mi} />
      </div>

      <dl className="mt-2 grid grid-cols-4 gap-1 text-center text-[11px] text-gray-500">
        <Metric label="No Travel" value={`${Math.round(summary.no_travel_miles)} mi`} />
        <Metric label="Severe" value={`${Math.round(summary.severe_miles)} mi`} />
        <Metric label="High" value={`${Math.round(summary.high_miles)} mi`} />
        <Metric label="Avg risk" value={summary.avg_risk.toFixed(2)} />
      </dl>

      {reason && (
        <p className="mt-2 rounded bg-emerald-50 px-2 py-1.5 text-xs text-emerald-900">{reason}</p>
      )}
    </button>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className="text-sm font-medium text-gray-900">{value}</dd>
    </div>
  )
}
