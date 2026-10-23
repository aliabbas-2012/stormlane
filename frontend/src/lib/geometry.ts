import type { Feature, FeatureCollection, LineString, Point } from 'geojson'

import type { Analysis, Route } from '../types/api'

type Position = [number, number]

/** Index i such that miles[i] <= mile < miles[i + 1] (clamped). */
function locate(miles: number[], mile: number): number {
  let lo = 0
  let hi = miles.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (miles[mid] <= mile) lo = mid
    else hi = mid
  }
  return lo
}

export function interpolate(route: Route, mile: number): Position {
  const { coordinates } = route.geometry
  const miles = route.geometry_miles
  const i = locate(miles, mile)
  const span = miles[i + 1] - miles[i]
  const t = span > 0 ? Math.min(Math.max((mile - miles[i]) / span, 0), 1) : 0
  const [x1, y1] = coordinates[i]
  const [x2, y2] = coordinates[Math.min(i + 1, coordinates.length - 1)]
  return [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]
}

/** The part of the route geometry between two miles, with interpolated end points. */
export function sliceByMiles(route: Route, fromMile: number, toMile: number): Position[] {
  const miles = route.geometry_miles
  const start = locate(miles, fromMile)
  const end = locate(miles, toMile)
  const inner = route.geometry.coordinates.slice(start + 1, end + 1)
  return [interpolate(route, fromMile), ...inner, interpolate(route, toMile)]
}

export interface SegmentProps {
  routeId: string
  level: number
}

/** One feature per risk segment of every route, so lines can be coloured by level. */
export function segmentFeatures(analysis: Analysis): FeatureCollection<LineString, SegmentProps> {
  const features: Feature<LineString, SegmentProps>[] = analysis.routes.flatMap((route) =>
    route.segments.map((segment) => ({
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: sliceByMiles(route, segment.from_mile, segment.to_mile),
      },
      properties: { routeId: route.id, level: segment.level },
    })),
  )
  return { type: 'FeatureCollection', features }
}

export interface CheckpointProps {
  routeId: string
  index: number
  level: number
}

export function checkpointFeatures(analysis: Analysis): FeatureCollection<Point, CheckpointProps> {
  const features: Feature<Point, CheckpointProps>[] = analysis.routes.flatMap((route) =>
    route.checkpoints.map((cp, index) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [cp.lon, cp.lat] },
      properties: { routeId: route.id, index, level: cp.level },
    })),
  )
  return { type: 'FeatureCollection', features }
}

export function routesBounds(analysis: Analysis): [Position, Position] {
  let [minX, minY, maxX, maxY] = [Infinity, Infinity, -Infinity, -Infinity]
  for (const route of analysis.routes) {
    for (const [x, y] of route.geometry.coordinates) {
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x)
      maxY = Math.max(maxY, y)
    }
  }
  return [
    [minX, minY],
    [maxX, maxY],
  ]
}

/** Position after `elapsedS` seconds of driving, clamped to the route's ends. */
export function positionAtElapsed(route: Route, elapsedS: number): Position {
  const times = route.geometry_elapsed_s
  const { coordinates } = route.geometry
  if (elapsedS <= 0) return coordinates[0]
  if (elapsedS >= times[times.length - 1]) return coordinates[coordinates.length - 1]
  const i = locate(times, elapsedS)
  const span = times[i + 1] - times[i]
  const t = span > 0 ? (elapsedS - times[i]) / span : 0
  const [x1, y1] = coordinates[i]
  const [x2, y2] = coordinates[i + 1]
  return [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]
}
