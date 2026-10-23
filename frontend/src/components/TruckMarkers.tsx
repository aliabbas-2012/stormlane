import { Marker } from 'react-map-gl/maplibre'

import { positionAtElapsed } from '../lib/geometry'
import type { Analysis } from '../types/api'

interface Props {
  analysis: Analysis
  /** UTC instant the slider points at. */
  at: Date
  selectedRouteId: string | null
}

/** Where each truck would be at the slider time: makes "weather at the truck's ETA" visible.
 * DOM markers move with a CSS transform, so this never touches a map source either. */
export function TruckMarkers({ analysis, at, selectedRouteId }: Props) {
  const elapsed = (at.getTime() - new Date(analysis.departure_time).getTime()) / 1000
  return analysis.routes.map((route) => {
    const [lon, lat] = positionAtElapsed(route, elapsed)
    const selected = route.id === selectedRouteId
    const status =
      elapsed < 0 ? 'not departed' : elapsed >= route.duration_s ? 'arrived' : 'en route'
    return (
      <Marker key={route.id} longitude={lon} latitude={lat} style={{ zIndex: selected ? 3 : 2 }}>
        <div
          title={`${route.name}: ${status}`}
          className={`flex items-center justify-center rounded-full border-2 border-white font-bold text-white shadow-md ${
            selected ? 'size-7 bg-slate-900 text-xs' : 'size-5 bg-slate-500 text-[10px]'
          }`}
        >
          {route.id}
        </div>
      </Marker>
    )
  })
}
