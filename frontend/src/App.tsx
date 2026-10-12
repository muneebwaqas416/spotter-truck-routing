import { TopBar } from '@/components/layout/TopBar'
import { LegendCard } from '@/components/map/LegendCard'
import {
  EmptyMapCard,
  HeatmapToggle,
  LoadingPill,
  MapErrorCard,
} from '@/components/map/MapOverlays'
import { MapView } from '@/components/map/MapView'
import { describeError } from '@/features/analysis/describeError'
import { ForecastSlider } from '@/features/heatmap/ForecastSlider'
import { useHeatmap } from '@/features/heatmap/useHeatmap'
import { useHeatmapToasts } from '@/features/heatmap/useHeatmapToasts'
import { SidePanel } from '@/features/trip/SidePanel'
import {
  forecastHourChanged,
  heatmapEnabledChanged,
  legendToggled,
} from '@/features/trip/tripSlice'
import { useAnalysis } from '@/features/trip/useAnalysis'
import { useAnalysisToasts } from '@/features/trip/useAnalysisToasts'
import { useAppDispatch, useAppSelector } from '@/redux/hooks'
import { heatmapRequestFor } from '@/features/heatmap/useHeatmap'

export default function App() {
  const dispatch = useAppDispatch()
  const analysis = useAnalysis()
  const results = analysis.isSuccess ? analysis.data : undefined
  const heatmap = useHeatmap(results)
  const forecastHour = useAppSelector((state) => state.trip.forecastHour)
  const legendOpen = useAppSelector((state) => state.trip.legendOpen)
  useAnalysisToasts()
  useHeatmapToasts(heatmap)

  const heatmapStart = results ? heatmapRequestFor(results)?.start : undefined

  return (
    <div className="flex h-dvh flex-col">
      <TopBar />
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <SidePanel />
        <main className="relative min-h-[60vh] flex-1">
          <MapView
            analysis={results}
            heatmap={heatmap.data}
            showHeatmap={heatmap.enabled}
            dimmed={analysis.isLoading || analysis.isError}
          />

          <div className="pointer-events-none absolute inset-0 z-10 flex flex-col p-4">
            <div className="flex justify-center gap-3 pr-12">
              {analysis.isLoading && <LoadingPill />}
              {results && (
                <div className="ml-auto">
                  <HeatmapToggle
                    enabled={heatmap.enabled}
                    status={heatmap.isLoading ? 'loading' : heatmap.error ? 'error' : 'ready'}
                    errorMessage={heatmap.error && describeError(heatmap.error).title}
                    onToggle={(enabled) => dispatch(heatmapEnabledChanged(enabled))}
                    onRetry={() => void heatmap.refetch()}
                  />
                </div>
              )}
            </div>

            <div className="flex flex-1 items-center justify-center">
              {!analysis.request && <EmptyMapCard />}
              {analysis.isError && analysis.error && (
                <MapErrorCard
                  title={describeError(analysis.error).title}
                  onRetry={
                    describeError(analysis.error).retryable
                      ? () => void analysis.refetch()
                      : undefined
                  }
                />
              )}
            </div>

            <div className="flex flex-col items-center gap-3 md:flex-row md:items-end">
              {legendOpen && (
                <div className="pointer-events-auto self-start md:self-end">
                  <LegendCard onClose={() => dispatch(legendToggled())} />
                </div>
              )}
              {results && heatmap.enabled && heatmapStart && (
                <div className="pointer-events-auto flex flex-1 justify-center">
                  <ForecastSlider
                    start={heatmapStart}
                    timeZone={results.origin.time_zone}
                    hour={forecastHour}
                    onHourChange={(hour) => dispatch(forecastHourChanged(hour))}
                    isLoading={heatmap.isLoading}
                    hasError={Boolean(heatmap.error)}
                    onRetry={() => void heatmap.refetch()}
                    missingByHour={heatmap.missingByHour}
                  />
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
