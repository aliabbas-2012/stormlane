import { formatDateTime } from '../lib/format'
import { RISK_COLORS, RISK_LABELS } from '../lib/risk'
import type { Checkpoint } from '../types/api'

export function CheckpointPopup({
  routeName,
  checkpoint,
}: {
  routeName: string
  checkpoint: Checkpoint
}) {
  const cp = checkpoint
  return (
    <div className="min-w-52 text-xs text-gray-800">
      <div className="flex items-center gap-2">
        <span
          className="size-3 rounded-full ring-1 ring-black/10"
          style={{ backgroundColor: RISK_COLORS[cp.level] }}
        />
        <span className="text-sm font-semibold">{RISK_LABELS[cp.level]}</span>
        <span className="ml-auto text-gray-500">
          {routeName} · mile {Math.round(cp.mile)}
        </span>
      </div>
      <div className="mt-1 text-gray-600">ETA {formatDateTime(cp.eta)}</div>
      <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5">
        <dt className="text-gray-500">Wind</dt>
        <dd>
          {Math.round(cp.wind_mph)} mph{' '}
          <span className="text-gray-500">(gust {Math.round(cp.gust_mph)})</span>
        </dd>
        <dt className="text-gray-500">Rain</dt>
        <dd>{cp.rain_in_hr.toFixed(2)} in/hr</dd>
        <dt className="text-gray-500">Snow</dt>
        <dd>{cp.snow_in_hr.toFixed(2)} in/hr</dd>
      </dl>
      <p className="mt-2 rounded bg-gray-50 px-2 py-1 text-gray-700">{cp.reason}</p>
    </div>
  )
}
