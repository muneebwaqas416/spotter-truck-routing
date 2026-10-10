import { WifiOff } from 'lucide-react'
import { useMemo } from 'react'

import { StatusAlert } from '@/components/StatusAlert'
import { Card } from '@/components/ui/card'
import { AnalysisProgress } from '@/features/analysis/AnalysisProgress'
import { ErrorAlert } from '@/features/analysis/ErrorAlert'
import { ResultsPanel } from '@/features/results/ResultsPanel'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { useAppSelector } from '@/redux/hooks'

import { TripForm } from './TripForm'
import { TripSummary } from './TripSummary'
import { useAnalysis } from './useAnalysis'
import { serverFieldErrors } from './validation'

export function SidePanel() {
  const online = useOnlineStatus()
  const isEditing = useAppSelector((state) => state.trip.isEditing)
  const submittedAt = useAppSelector((state) => state.trip.submittedAt)
  const analysis = useAnalysis()
  const fieldErrors = analysis.error?.status === 400 ? analysis.error.fieldErrors : undefined
  // Stable identity so the form only re-applies server errors when they actually change.
  const serverErrors = useMemo(() => serverFieldErrors(fieldErrors), [fieldErrors])
  const showForm = isEditing || analysis.isLoading || analysis.isError || !analysis.request

  return (
    <aside className="flex w-full shrink-0 flex-col overflow-y-auto border-border bg-white md:w-96 md:border-r">
      <div className="space-y-5 p-5">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Route Weather Analysis</h1>
          <p className="text-sm text-muted-foreground">Safest route by weather, load &amp; time</p>
        </div>

        {!online && (
          <StatusAlert tone="info" icon={WifiOff} title="You're offline">
            Check your connection. Results already loaded stay available.
          </StatusAlert>
        )}

        {showForm ? (
          <Card className="bg-muted/50 px-4">
            <TripForm
              // Remount when a new request is submitted so the form reflects it.
              key={analysis.request?.departure_time ?? 'new'}
              initialRequest={analysis.request}
              isLoading={analysis.isLoading}
              serverErrors={serverErrors}
              canClose={Boolean(analysis.data) && !analysis.isLoading}
            />
          </Card>
        ) : (
          analysis.request && <TripSummary request={analysis.request} />
        )}

        {analysis.isLoading && <AnalysisProgress />}
        {analysis.isError && analysis.error && (
          // Keyed by submission so the countdown and details reset for each new failure.
          <ErrorAlert key={submittedAt} error={analysis.error} onRetry={analysis.refetch} />
        )}
        {analysis.isSuccess && analysis.data && !isEditing && (
          <ResultsPanel analysis={analysis.data} />
        )}

        {!analysis.request && <GettingStarted />}
      </div>
    </aside>
  )
}

function GettingStarted() {
  const steps = [
    'We get 3 truck routes between your stops.',
    'Weather is sampled at your ETA every 10, 25 or 50 miles.',
    'Routes are ranked by Severe miles, High miles, average risk, then time.',
  ]
  return (
    <div className="rounded-xl border border-dashed border-input p-4">
      <p className="text-sm font-semibold text-foreground">How it works</p>
      <ol className="mt-3 space-y-2">
        {steps.map((step, index) => (
          <li key={step} className="flex gap-3 text-sm text-muted-foreground">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-xs text-foreground">
              {index + 1}
            </span>
            {step}
          </li>
        ))}
      </ol>
    </div>
  )
}
