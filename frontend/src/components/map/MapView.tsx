import 'maplibre-gl/dist/maplibre-gl.css'

import { COORDINATE_SYSTEM, type PickingInfo } from '@deck.gl/core'
import { BitmapLayer, PathLayer, ScatterplotLayer } from '@deck.gl/layers'
import { MapboxOverlay, type MapboxOverlayProps } from '@deck.gl/mapbox'
import { useCallback, useEffect, useMemo, useRef } from 'react'
import MapGL, {
  AttributionControl,
  NavigationControl,
  Popup,
  useControl,
  type MapRef,
} from 'react-map-gl/maplibre'

import type {
  AnalyzeResponse,
  Checkpoint,
  HeatmapResponse,
  LngLat,
  RouteOption,
} from '@/redux/types'
import { useAppDispatch, useAppSelector } from '@/redux/hooks'
import { routesBBox } from '@/features/results/derive'
import { checkpointSelected, routeSelected } from '@/features/trip/tripSlice'
import { env } from '@/config/env'
import { RISK_STYLES } from '@/lib/risk'

import { CheckpointPopup } from './CheckpointPopup'
import { gridToImage } from './heatmapGrid'
import { cn } from '@/lib/utils'

const INITIAL_VIEW = { longitude: -98.5, latitude: 39.8, zoom: 3.6 } // continental US
const SELECTED_ROUTE_COLOR: [number, number, number] = [29, 78, 216]
const OTHER_ROUTE_COLOR: [number, number, number] = [148, 163, 184]
interface CheckpointDatum extends Checkpoint {
  routeId: string
  selectedRoute: boolean
}

interface MapViewProps {
  analysis: AnalyzeResponse | undefined
  heatmap: HeatmapResponse | undefined
  showHeatmap: boolean
  dimmed: boolean
}

function DeckOverlay(props: MapboxOverlayProps) {
  const overlay = useControl<MapboxOverlay>(() => new MapboxOverlay(props))
  overlay.setProps(props)
  return null
}

export function MapView({ analysis, heatmap, showHeatmap, dimmed }: MapViewProps) {
  const dispatch = useAppDispatch()
  const mapRef = useRef<MapRef>(null)
  const selectedRouteId = useAppSelector((state) => state.trip.selectedRouteId)
  const selectedCheckpoint = useAppSelector((state) => state.trip.selectedCheckpoint)
  const forecastHour = useAppSelector((state) => state.trip.forecastHour)

  const activeRouteId = selectedRouteId ?? analysis?.recommendation.route_id

  // Fit the camera to the routes once per analysis, and again when the map (re)loads,
  // since results can arrive before MapLibre has finished initialising.
  const fitToRoutes = useCallback(() => {
    const bbox = analysis && routesBBox(analysis.routes)
    if (!bbox) return
    mapRef.current?.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: { top: 90, bottom: 220, left: 60, right: 60 }, duration: 800 },
    )
  }, [analysis])

  useEffect(fitToRoutes, [fitToRoutes])

  // Draw the active route last so it sits on top.
  const orderedRoutes = useMemo<RouteOption[]>(() => {
    if (!analysis) return []
    return [...analysis.routes].sort(
      (a, b) => Number(a.id === activeRouteId) - Number(b.id === activeRouteId),
    )
  }, [analysis, activeRouteId])

  const checkpoints = useMemo<CheckpointDatum[]>(
    () =>
      orderedRoutes.flatMap((route) =>
        route.checkpoints.map((checkpoint) => ({
          ...checkpoint,
          routeId: route.id,
          selectedRoute: route.id === activeRouteId,
        })),
      ),
    [orderedRoutes, activeRouteId],
  )

  // Only the hour's texture is rebuilt when the slider moves (~300 pixels); no refetch.
  const heatImage = useMemo(() => {
    const scores = heatmap?.scores[forecastHour]
    if (!heatmap || !scores) return undefined
    const grid = gridToImage(heatmap.points, scores)
    return grid && { image: new ImageData(grid.data, grid.width, grid.height), bounds: grid.bounds }
  }, [heatmap, forecastHour])

  const layers = [
    showHeatmap &&
      heatImage &&
      new BitmapLayer({
        id: 'weather-heatmap',
        image: heatImage.image,
        bounds: heatImage.bounds,
        // Bilinear filtering turns the coarse forecast grid into a smooth surface.
        textureParameters: { minFilter: 'linear', magFilter: 'linear' },
        // The grid is evenly spaced in latitude. By default the image is stretched evenly in
        // Web Mercator, which drew rows up to ~50 mi north of their forecast point.
        _imageCoordinateSystem: COORDINATE_SYSTEM.LNGLAT,
      }),
    new PathLayer<RouteOption>({
      id: 'routes',
      data: orderedRoutes,
      getPath: (route) => route.geometry,
      getColor: (route) => (route.id === activeRouteId ? SELECTED_ROUTE_COLOR : OTHER_ROUTE_COLOR),
      getWidth: (route) => (route.id === activeRouteId ? 7 : 4),
      widthUnits: 'pixels',
      capRounded: true,
      jointRounded: true,
      pickable: true,
      onClick: ({ object }: PickingInfo<RouteOption>) => {
        if (object) dispatch(routeSelected(object.id))
      },
      updateTriggers: { getColor: activeRouteId, getWidth: activeRouteId },
    }),
    new ScatterplotLayer<CheckpointDatum>({
      id: 'checkpoints',
      data: checkpoints,
      getPosition: (d) => d.position,
      getRadius: (d) => (d.selectedRoute ? 6 : 4),
      radiusUnits: 'pixels',
      stroked: true,
      lineWidthUnits: 'pixels',
      getLineWidth: (d) => (d.risk === 'UNKNOWN' ? 2 : 1.5),
      getLineColor: (d) => (d.risk === 'UNKNOWN' ? RISK_STYLES.UNKNOWN.rgb : [255, 255, 255]),
      getFillColor: (d) => (d.risk === 'UNKNOWN' ? [255, 255, 255] : RISK_STYLES[d.risk].rgb),
      pickable: true,
      onClick: ({ object }: PickingInfo<CheckpointDatum>) => {
        if (object) dispatch(checkpointSelected({ routeId: object.routeId, index: object.index }))
      },
      updateTriggers: { getRadius: activeRouteId },
    }),
    analysis &&
      new ScatterplotLayer<{ position: LngLat }>({
        id: 'endpoints',
        data: [analysis.origin, analysis.destination],
        getPosition: (d) => d.position,
        getRadius: 7,
        radiusUnits: 'pixels',
        stroked: true,
        lineWidthUnits: 'pixels',
        getLineWidth: 3,
        getLineColor: [255, 255, 255],
        getFillColor: [15, 23, 42],
      }),
  ].filter(Boolean)

  const popup = useMemo(() => {
    if (!analysis || !selectedCheckpoint) return null
    const route = analysis.routes.find((r) => r.id === selectedCheckpoint.routeId)
    const checkpoint = route?.checkpoints.find((c) => c.index === selectedCheckpoint.index)
    return route && checkpoint ? { route, checkpoint } : null
  }, [analysis, selectedCheckpoint])

  return (
    <div className={cn('h-full w-full transition-[filter]', dimmed && 'grayscale-[60%]')}>
      <MapGL
        ref={mapRef}
        initialViewState={INITIAL_VIEW}
        mapStyle={env.mapStyleUrl}
        style={{ width: '100%', height: '100%' }}
        onClick={() => selectedCheckpoint && dispatch(checkpointSelected(null))}
        onLoad={fitToRoutes}
        attributionControl={false}
      >
        {/* Open-Meteo's free data is CC BY 4.0, which requires attribution next to the map's own. */}
        <AttributionControl customAttribution='<a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Weather data by Open-Meteo.com</a>' />
        <NavigationControl position="top-right" showCompass={false} />
        <DeckOverlay
          layers={layers}
          interleaved={false}
          getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
        />
        {popup && (
          <Popup
            longitude={popup.checkpoint.position[0]}
            latitude={popup.checkpoint.position[1]}
            offset={12}
            maxWidth="none"
            closeOnClick={false}
            // Our own close button lives inside the popup content (CheckpointPopup).
            closeButton={false}
            onClose={() => dispatch(checkpointSelected(null))}
          >
            <CheckpointPopup
              checkpoint={popup.checkpoint}
              routeLabel={popup.route.label}
              timeZone={analysis?.origin.time_zone ?? 'UTC'}
              onClose={() => dispatch(checkpointSelected(null))}
            />
          </Popup>
        )}
      </MapGL>
    </div>
  )
}
