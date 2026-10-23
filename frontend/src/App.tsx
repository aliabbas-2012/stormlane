import { type CSSProperties, useCallback, useEffect, useRef, useState } from 'react'

import { useAnalyze, useHealth, useHeatmap } from './api/hooks'
import { Legend } from './components/Legend'
import { type CheckpointRef, MapView } from './components/MapView'
import { Notices } from './components/Notices'
import { RouteCards } from './components/RouteCards'
import { RouteCardsSkeleton } from './components/RouteCardsSkeleton'
import { RouteDetail } from './components/RouteDetail'
import { TimeSlider } from './components/TimeSlider'
import { Toast } from './components/Toast'
import { TripForm } from './components/TripForm'
import { formatDateTime, formatLbs } from './lib/format'
import { HEATMAP_HOURS } from './lib/heatmap'
import type { AnalyzeRequest, HeatmapMetric } from './types/api'

const PLAY_FRAME_MS = 250
// Phone layout: the panel is a bottom sheet over a full-screen map.
const SHEET_PEEK = '45%'
const SHEET_OPEN = '88%'

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
  const [hour, setHour] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [metric, setMetric] = useState<HeatmapMetric>('risk')
  const [showHeatmap, setShowHeatmap] = useState(true)
  const [sheetOpen, setSheetOpen] = useState(false)
  const resultsRef = useRef<HTMLDivElement>(null)

  const analysis = analyze.data ?? null
  const current =
    selection && analysis && selection.analysisId === analysis.analysis_id ? selection : null
  const selectedRouteId = current?.routeId ?? analysis?.recommended_route_id ?? null
  const selectedCheckpoint = current?.checkpoint ?? null
  const selectedRoute = analysis?.routes.find((r) => r.id === selectedRouteId) ?? null
  const shownAnalysis = analyze.isPending ? null : analysis
  const heatmap = useHeatmap(shownAnalysis?.analysis_id ?? null)
  const heatmapData =
    heatmap.data && heatmap.data.analysis_id === shownAnalysis?.analysis_id ? heatmap.data : null
  const hourIso = heatmapData?.hours[hour] ?? null

  // On phones the form fills the bottom sheet, so bring a new analysis into view. Desktop
  // keeps the form visible for tweaking the trip.
  const shownId = shownAnalysis?.analysis_id
  useEffect(() => {
    if (shownId && !window.matchMedia('(min-width: 768px)').matches) {
      resultsRef.current?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    }
  }, [shownId])

  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => setHour((h) => (h + 1) % HEATMAP_HOURS), PLAY_FRAME_MS)
    return () => window.clearInterval(timer)
  }, [playing])

  const select = useCallback(
    (routeId: string | null, checkpoint: CheckpointRef | null) => {
      if (analysis) setSelection({ analysisId: analysis.analysis_id, routeId, checkpoint })
    },
    [analysis],
  )
  const dismissError = useCallback(() => setDismissedError(analyze.error), [analyze.error])

  function submit(request: AnalyzeRequest) {
    setHour(0)
    setPlaying(false)
    analyze.mutate(request)
  }

  const errorMessage =
    analyze.error && analyze.error !== dismissedError ? analyze.error.message : null

  return (
    <div
      className="relative h-full md:flex md:flex-row"
      style={{ '--sheet-h': sheetOpen ? SHEET_OPEN : SHEET_PEEK } as CSSProperties}
    >
      <aside className="absolute inset-x-0 bottom-0 z-20 flex h-(--sheet-h) flex-col overflow-y-auto rounded-t-2xl border-gray-200 bg-gray-50 shadow-[0_-8px_24px_rgba(15,23,42,0.18)] transition-[height] duration-300 md:static md:z-auto md:h-full md:w-[380px] md:shrink-0 md:rounded-none md:border-r md:shadow-none md:transition-none">
        <button
          type="button"
          onClick={() => setSheetOpen((open) => !open)}
          aria-expanded={sheetOpen}
          className="sticky top-0 z-10 flex w-full flex-col items-center gap-1 bg-gray-50 pt-2 pb-1 text-[11px] text-gray-500 md:hidden"
        >
          <span className="h-1.5 w-10 rounded-full bg-gray-300" aria-hidden="true" />
          {sheetOpen ? 'Show more map' : 'Show more details'}
        </button>
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
            <div ref={resultsRef} className="scroll-mt-10 space-y-4">
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
              <div className="md:hidden">
                <Legend />
              </div>
            </div>
          )}

          {!analyze.isPending && !analysis && (
            <p className="rounded-md border border-gray-200 bg-white p-3 text-xs text-gray-600">
              Enter a trip to compare up to three routes. Weather is checked at each checkpoint for
              the time the truck is expected to reach it, not the departure time.
            </p>
          )}
        </div>
      </aside>

      <main className="absolute inset-0 md:relative md:inset-auto md:h-full md:flex-1">
        <MapView
          analysis={shownAnalysis}
          heatmap={{
            data: heatmapData,
            hour,
            metric,
            visible: showHeatmap,
            at: hourIso ? new Date(hourIso) : null,
          }}
          selectedRouteId={selectedRouteId}
          selectedCheckpoint={selectedCheckpoint}
          onSelectRoute={(routeId) => select(routeId, null)}
          onSelectCheckpoint={(checkpoint) =>
            select(checkpoint?.routeId ?? selectedRouteId, checkpoint)
          }
        />
        {shownAnalysis && (
          <div className="absolute bottom-[calc(var(--sheet-h)+8px)] left-1/2 z-10 -translate-x-1/2 md:bottom-8">
            <TimeSlider
              hours={heatmapData?.hours ?? []}
              hour={hour}
              onHour={(h) => {
                setPlaying(false)
                setHour(h)
              }}
              playing={playing}
              onTogglePlay={() => setPlaying((p) => !p)}
              metric={metric}
              onMetric={setMetric}
              visible={showHeatmap}
              onVisible={setShowHeatmap}
              status={heatmapData ? 'ready' : heatmap.isError ? 'error' : 'loading'}
            />
          </div>
        )}
      </main>

      {errorMessage && <Toast message={errorMessage} onDismiss={dismissError} />}
    </div>
  )
}
