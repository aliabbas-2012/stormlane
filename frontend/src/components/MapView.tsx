import 'maplibre-gl/dist/maplibre-gl.css'

import Map, { NavigationControl } from 'react-map-gl/maplibre'

const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'

// Continental US; refit to routes once an analysis exists.
const INITIAL_VIEW = { longitude: -98.5, latitude: 39.5, zoom: 3.6 }

export function MapView() {
  return (
    <Map
      initialViewState={INITIAL_VIEW}
      mapStyle={MAP_STYLE}
      style={{ width: '100%', height: '100%' }}
    >
      <NavigationControl position="top-right" />
    </Map>
  )
}
