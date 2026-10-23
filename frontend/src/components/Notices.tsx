import type { Analysis } from '../types/api'

export function Notices({ analysis }: { analysis: Analysis }) {
  return (
    <div className="space-y-2">
      {analysis.no_safe_route && (
        <div
          role="alert"
          className="rounded-md border border-purple-300 bg-purple-50 p-3 text-sm text-purple-950"
        >
          <p className="font-semibold">No safe route at this departure time</p>
          <p className="mt-0.5 text-xs">
            Every route crosses a No Travel zone. Consider delaying departure; routes are still
            ranked below.
          </p>
        </div>
      )}
      {analysis.warnings.map((warning) => (
        <p
          key={warning}
          className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900"
        >
          {warning}
        </p>
      ))}
    </div>
  )
}
