import 'maplibre-gl/dist/maplibre-gl.css'

import type { ExpressionSpecification } from 'maplibre-gl'
import { useEffect, useMemo, useRef, useState } from 'react'
import Map, {
  Layer,
  type MapLayerMouseEvent,
  type MapRef,
  Marker,
  NavigationControl,
  Popup,
  Source,
} from 'react-map-gl/maplibre'

import { checkpointFeatures, routesBounds, segmentFeatures } from '../lib/geometry'
import { RISK_COLOR_EXPRESSION } from '../lib/risk'
import type { Analysis } from '../types/api'
import { CheckpointPopup } from './CheckpointPopup'
import { Legend } from './Legend'

const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
// Continental US until an analysis exists.
const INITIAL_VIEW = { longitude: -98.5, latitude: 39.5, zoom: 3.6 }
const INTERACTIVE_LAYERS = ['checkpoints', 'routes-selected', 'routes-dim']

export interface CheckpointRef {
  routeId: string
  index: number
}

interface Props {
  analysis: Analysis | null
  selectedRouteId: string | null
  selectedCheckpoint: CheckpointRef | null
  onSelectRoute: (routeId: string) => void
  onSelectCheckpoint: (ref: CheckpointRef | null) => void
}

export function MapView({
  analysis,
  selectedRouteId,
  selectedCheckpoint,
  onSelectRoute,
  onSelectCheckpoint,
}: Props) {
  const mapRef = useRef<MapRef>(null)
  const [cursor, setCursor] = useState<string>('')

  // GeoJSON is rebuilt only when a new analysis arrives; selecting a route just swaps
  // layer filters, so the sources are never re-uploaded on interaction.
  const segments = useMemo(() => (analysis ? segmentFeatures(analysis) : null), [analysis])
  const checkpoints = useMemo(() => (analysis ? checkpointFeatures(analysis) : null), [analysis])

  useEffect(() => {
    if (!analysis) return
    mapRef.current?.fitBounds(routesBounds(analysis), { padding: 60, duration: 800 })
  }, [analysis])

  const isSelected: ExpressionSpecification = ['==', ['get', 'routeId'], selectedRouteId ?? '']
  const notSelected: ExpressionSpecification = ['!=', ['get', 'routeId'], selectedRouteId ?? '']

  function onClick(event: MapLayerMouseEvent) {
    const feature = event.features?.[0]
    if (!feature) {
      onSelectCheckpoint(null)
      return
    }
    const props = feature.properties as { routeId: string; index?: number }
    if (feature.layer.id === 'checkpoints' && props.index !== undefined) {
      onSelectCheckpoint({ routeId: props.routeId, index: props.index })
    } else {
      onSelectRoute(props.routeId)
    }
  }

  const popupRoute = analysis?.routes.find((r) => r.id === selectedCheckpoint?.routeId)
  const popupCheckpoint = selectedCheckpoint && popupRoute?.checkpoints[selectedCheckpoint.index]

  return (
    <Map
      ref={mapRef}
      initialViewState={INITIAL_VIEW}
      mapStyle={MAP_STYLE}
      style={{ width: '100%', height: '100%' }}
      interactiveLayerIds={analysis ? INTERACTIVE_LAYERS : []}
      cursor={cursor}
      // Compact attribution: the full-width bar covered the legend on phones.
      attributionControl={{ compact: true }}
      onMouseEnter={() => setCursor('pointer')}
      onMouseLeave={() => setCursor('')}
      onClick={onClick}
    >
      <NavigationControl position="top-right" />

      {segments && (
        <Source id="routes" type="geojson" data={segments}>
          <Layer
            id="routes-dim"
            type="line"
            filter={notSelected}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
            paint={{ 'line-color': RISK_COLOR_EXPRESSION, 'line-width': 3.5, 'line-opacity': 0.45 }}
          />
          <Layer
            id="routes-casing"
            type="line"
            filter={isSelected}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
            paint={{ 'line-color': '#ffffff', 'line-width': 10 }}
          />
          <Layer
            id="routes-selected"
            type="line"
            filter={isSelected}
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
            paint={{ 'line-color': RISK_COLOR_EXPRESSION, 'line-width': 6 }}
          />
        </Source>
      )}

      {checkpoints && (
        <Source id="checkpoints" type="geojson" data={checkpoints}>
          <Layer
            id="checkpoints"
            type="circle"
            filter={isSelected}
            paint={{
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3.5, 9, 7],
              'circle-color': RISK_COLOR_EXPRESSION,
              'circle-stroke-color': '#ffffff',
              'circle-stroke-width': 1.5,
            }}
          />
        </Source>
      )}

      {analysis && (
        <>
          <Marker longitude={analysis.origin.lon} latitude={analysis.origin.lat} color="#0f172a" />
          <Marker
            longitude={analysis.destination.lon}
            latitude={analysis.destination.lat}
            color="#0369a1"
          />
        </>
      )}

      {popupRoute && popupCheckpoint && (
        <Popup
          longitude={popupCheckpoint.lon}
          latitude={popupCheckpoint.lat}
          onClose={() => onSelectCheckpoint(null)}
          closeOnClick={false}
          maxWidth="300px"
        >
          <CheckpointPopup routeName={popupRoute.name} checkpoint={popupCheckpoint} />
        </Popup>
      )}

      <div className="absolute bottom-6 left-3">
        <Legend />
      </div>
    </Map>
  )
}
