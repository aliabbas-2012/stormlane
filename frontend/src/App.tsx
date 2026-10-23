import { useCallback, useState } from 'react'

import { useAnalyze, useHealth } from './api/hooks'
import { type CheckpointRef, MapView } from './components/MapView'
import { Notices } from './components/Notices'
import { RouteCards } from './components/RouteCards'
import { RouteCardsSkeleton } from './components/RouteCardsSkeleton'
import { RouteDetail } from './components/RouteDetail'
import { Toast } from './components/Toast'
import { TripForm } from './components/TripForm'
import { formatDateTime, formatLbs } from './lib/format'
import type { AnalyzeRequest } from './types/api'

/** Selections are keyed by analysis id, so a new analysis resets them without an effect. */
interface Selection {
  analysisId: string
  routeId: string | null
  checkpoint: CheckpointRef | null
}

export default function App() {
  const health = useHealth()
  const analyze = useAnalyze()
  const [selection, setSelection] = useState<Selection | null>(null)
  const [dismissedError, setDismissedError] = useState<unknown>(null)

  const analysis = analyze.data ?? null
  const current =
    selection && analysis && selection.analysisId === analysis.analysis_id ? selection : null
  const selectedRouteId = current?.routeId ?? analysis?.recommended_route_id ?? null
  const selectedCheckpoint = current?.checkpoint ?? null
  const selectedRoute = analysis?.routes.find((r) => r.id === selectedRouteId) ?? null

  const select = useCallback(
    (routeId: string | null, checkpoint: CheckpointRef | null) => {
      if (analysis) setSelection({ analysisId: analysis.analysis_id, routeId, checkpoint })
    },
    [analysis],
  )
  const dismissError = useCallback(() => setDismissedError(analyze.error), [analyze.error])

  function submit(request: AnalyzeRequest) {
    analyze.mutate(request)
  }

  const errorMessage =
    analyze.error && analyze.error !== dismissedError ? analyze.error.message : null

  return (
    <div className="flex h-full flex-col md:flex-row">
      <aside className="order-2 flex w-full shrink-0 flex-col overflow-y-auto border-gray-200 bg-gray-50 md:order-1 md:h-full md:w-[380px] md:border-r">
        <header className="border-b border-gray-200 bg-white px-4 py-3">
          <h1 className="text-lg font-semibold text-gray-900">StormLane</h1>
          <p className="text-xs text-gray-500">
            Weather-aware truck routing: risk at each checkpoint&apos;s ETA
          </p>
        </header>

        <div className="space-y-4 p-4">
          {health.isError && (
            <p
              role="status"
              className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900"
            >
              The StormLane API is unreachable right now. Analysis will fail until it is back.
            </p>
          )}
          <TripForm isPending={analyze.isPending} showExample={!analysis} onSubmit={submit} />

          {analyze.isPending && <RouteCardsSkeleton />}

          {!analyze.isPending && analysis && (
            <>
              <p className="text-xs text-gray-500">
                {analysis.origin.label} → {analysis.destination.label} · departs{' '}
                {formatDateTime(analysis.departure_time)} · {formatLbs(analysis.load_lbs)} · every{' '}
                {analysis.interval_miles} mi
              </p>
              <Notices analysis={analysis} />
              <RouteCards
                analysis={analysis}
                selectedId={selectedRouteId ?? ''}
                onSelect={(routeId) => select(routeId, null)}
              />
              {selectedRoute && (
                <RouteDetail
                  route={selectedRoute}
                  selectedIndex={
                    selectedCheckpoint?.routeId === selectedRoute.id
                      ? selectedCheckpoint.index
                      : null
                  }
                  onSelectCheckpoint={(index) =>
                    select(selectedRoute.id, { routeId: selectedRoute.id, index })
                  }
                />
              )}
            </>
          )}

          {!analyze.isPending && !analysis && (
            <p className="rounded-md border border-gray-200 bg-white p-3 text-xs text-gray-600">
              Enter a trip to compare up to three routes. Weather is checked at each checkpoint for
              the time the truck is expected to reach it, not the departure time.
            </p>
          )}
        </div>
      </aside>

      <main className="relative order-1 h-[55vh] shrink-0 md:order-2 md:h-full md:flex-1">
        <MapView
          analysis={analyze.isPending ? null : analysis}
          selectedRouteId={selectedRouteId}
          selectedCheckpoint={selectedCheckpoint}
          onSelectRoute={(routeId) => select(routeId, null)}
          onSelectCheckpoint={(checkpoint) =>
            select(checkpoint?.routeId ?? selectedRouteId, checkpoint)
          }
        />
      </main>

      {errorMessage && <Toast message={errorMessage} onDismiss={dismissError} />}
    </div>
  )
}
