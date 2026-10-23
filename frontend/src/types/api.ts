/** Mirrors the backend response contract of POST /api/analyze and GET /api/geocode. */

/** 0 Low, 1 Moderate, 2 High, 3 Severe, 4 No Travel. */
export type RiskLevel = 0 | 1 | 2 | 3 | 4

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface Checkpoint {
  mile: number
  lat: number
  lon: number
  eta: string
  forecast_hour: string
  wind_mph: number
  gust_mph: number
  rain_in_hr: number
  snow_in_hr: number
  level: RiskLevel
  drivers: string[]
  reason: string
}

export interface RouteSummary {
  no_travel_miles: number
  severe_miles: number
  high_miles: number
  moderate_miles: number
  low_miles: number
  avg_risk: number
  max_level: RiskLevel
  worst_checkpoint: { index: number; mile: number; level: RiskLevel; reason: string }
}

export interface RiskSegment {
  from_mile: number
  to_mile: number
  level: RiskLevel
}

export interface Route {
  id: string
  name: string
  provider: string
  synthesized: boolean
  timing_source: 'segments' | 'proportional'
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  /** Mile and elapsed seconds at each geometry vertex, measured on the full route. */
  geometry_miles: number[]
  geometry_elapsed_s: number[]
  distance_mi: number
  duration_s: number
  arrival_time: string
  summary: RouteSummary
  checkpoints: Checkpoint[]
  segments: RiskSegment[]
}

export interface Analysis {
  analysis_id: string
  origin: Place
  destination: Place
  departure_time: string
  load_lbs: number
  interval_miles: IntervalMiles
  provider: string
  truck_profile: boolean
  routes: Route[]
  ranking: string[]
  recommended_route_id: string
  recommendation_reason: string
  no_safe_route: boolean
  warnings: string[]
}

export type IntervalMiles = 10 | 25 | 50

export interface AnalyzeRequest {
  origin: Place
  destination: Place
  departure_time: string
  load_lbs: number
  interval_miles: IntervalMiles
}
