import { RISK_COLORS, RISK_LABELS, RISK_LEVELS } from '../lib/risk'

export function Legend() {
  return (
    <div className="rounded-md bg-white/95 px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-semibold text-gray-700">Risk at truck ETA</div>
      <ul className="space-y-0.5">
        {RISK_LEVELS.map((level) => (
          <li key={level} className="flex items-center gap-2">
            <span
              className="h-1.5 w-5 rounded-full"
              style={{ backgroundColor: RISK_COLORS[level] }}
            />
            {RISK_LABELS[level]}
          </li>
        ))}
      </ul>
    </div>
  )
}
