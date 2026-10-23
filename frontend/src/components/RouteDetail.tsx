import { formatTime } from '../lib/format'
import { RISK_COLORS, RISK_LABELS } from '../lib/risk'
import type { Route } from '../types/api'

interface Props {
  route: Route
  selectedIndex: number | null
  onSelectCheckpoint: (index: number) => void
}

/** Checkpoint timeline of the selected route; clicking a row opens its popup on the map. */
export function RouteDetail({ route, selectedIndex, onSelectCheckpoint }: Props) {
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-900">
        {route.name} checkpoints{' '}
        <span className="font-normal text-gray-500">({route.checkpoints.length})</span>
      </h2>
      <ol className="mt-2 divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white text-xs">
        {route.checkpoints.map((cp, index) => (
          <li key={index}>
            <button
              type="button"
              onClick={() => onSelectCheckpoint(index)}
              className={`flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-gray-50 ${
                index === selectedIndex ? 'bg-sky-50' : ''
              }`}
            >
              <span
                className="mt-0.5 size-2.5 shrink-0 rounded-full ring-1 ring-black/10"
                style={{ backgroundColor: RISK_COLORS[cp.level] }}
              />
              <span className="w-12 shrink-0 tabular-nums text-gray-500">
                mi {Math.round(cp.mile)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-gray-900">
                  {formatTime(cp.eta)} ·{' '}
                  <span className="font-medium">{RISK_LABELS[cp.level]}</span>
                </span>
                {cp.level > 0 && <span className="block truncate text-gray-500">{cp.reason}</span>}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  )
}
