import { zodResolver } from '@hookform/resolvers/zod'
import { Clock, Route, Weight } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { Controller, useForm, useWatch } from 'react-hook-form'

import { InputIcon } from '@/components/InputIcon'
import { StatusAlert } from '@/components/StatusAlert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { addHours, nextFullHour, toLocalInputValue } from '@/lib/datetime'
import { useAppDispatch } from '@/redux/hooks'
import type { AnalyzeRequest } from '@/redux/types'

import { FieldError } from './FieldError'
import { IntervalControl } from './IntervalControl'
import { PlaceAutocomplete } from './PlaceAutocomplete'
import { analysisCancelled, analysisSubmitted, closeEditor } from './tripSlice'
import {
  FORECAST_HORIZON_DAYS,
  MAX_LOAD_LB,
  toAnalyzeRequest,
  tripSchema,
  type TripField,
  type TripFormErrors,
  type TripFormValues,
} from './validation'

interface TripFormProps {
  initialRequest: AnalyzeRequest | null
  isLoading: boolean
  serverErrors: TripFormErrors
  canClose: boolean
}

function defaultValues(request: AnalyzeRequest | null): TripFormValues {
  if (!request) {
    return {
      origin: '',
      destination: '',
      departure: toLocalInputValue(nextFullHour()),
      loadLb: '',
      intervalMi: 25,
    }
  }
  return {
    origin: request.origin,
    destination: request.destination,
    departure: toLocalInputValue(new Date(request.departure_time)),
    loadLb: request.load_lb.toLocaleString('en-US'),
    intervalMi: request.interval_mi,
  }
}

const parseLoad = (value: string) => Number(value.replace(/,/g, ''))

export function TripForm({ initialRequest, isLoading, serverErrors, canClose }: TripFormProps) {
  const dispatch = useAppDispatch()
  const ids = { departure: useId(), load: useId() }
  const {
    control,
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors, isSubmitted },
  } = useForm<TripFormValues>({
    resolver: zodResolver(tripSchema),
    defaultValues: defaultValues(initialRequest),
    mode: 'onTouched',
  })

  // Backend validation errors appear inline; editing the field re-validates and clears them.
  useEffect(() => {
    for (const [field, message] of Object.entries(serverErrors)) {
      setError(field as TripField, { type: 'server', message })
    }
  }, [serverErrors, setError])

  // Picker bounds are fixed when the form opens; validation re-checks against the current time.
  const [departureBounds] = useState(() => {
    const now = new Date()
    return {
      min: toLocalInputValue(addHours(now, -1)),
      max: toLocalInputValue(addHours(now, FORECAST_HORIZON_DAYS * 24)),
    }
  })

  const onSubmit = handleSubmit((values) => {
    dispatch(analysisSubmitted(toAnalyzeRequest(values)))
  })

  const load = parseLoad(useWatch({ control, name: 'loadLb' }))
  const errorCount = Object.keys(errors).length
  const blocked = isSubmitted && errorCount > 0

  return (
    <form noValidate onSubmit={onSubmit} className="space-y-4" aria-busy={isLoading}>
      <Controller
        control={control}
        name="origin"
        render={({ field, fieldState }) => (
          <PlaceAutocomplete
            label="Origin"
            dotClassName="bg-success"
            value={field.value}
            onChange={field.onChange}
            onBlur={field.onBlur}
            error={fieldState.error?.message}
            disabled={isLoading}
          />
        )}
      />
      <Controller
        control={control}
        name="destination"
        render={({ field, fieldState }) => (
          <PlaceAutocomplete
            label="Destination"
            dotClassName="bg-primary"
            value={field.value}
            onChange={field.onChange}
            onBlur={field.onBlur}
            error={fieldState.error?.message}
            disabled={isLoading}
          />
        )}
      />

      <div className="space-y-1.5">
        <Label htmlFor={ids.departure}>Departure</Label>
        <div className="relative">
          <InputIcon icon={Clock} />
          <Input
            id={ids.departure}
            type="datetime-local"
            min={departureBounds.min}
            max={departureBounds.max}
            disabled={isLoading}
            aria-invalid={Boolean(errors.departure)}
            aria-describedby={errors.departure ? `${ids.departure}-error` : undefined}
            className="h-10 bg-white pl-9"
            {...register('departure')}
          />
        </div>
        <FieldError id={`${ids.departure}-error`} message={errors.departure?.message} />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between">
          <Label htmlFor={ids.load}>Load weight</Label>
          <span className="text-xs text-muted-foreground">
            Max {MAX_LOAD_LB.toLocaleString('en-US')} lb
          </span>
        </div>
        <div className="relative">
          <InputIcon icon={Weight} />
          <Input
            id={ids.load}
            inputMode="numeric"
            placeholder="42,000"
            disabled={isLoading}
            aria-invalid={Boolean(errors.loadLb)}
            aria-describedby={errors.loadLb ? `${ids.load}-error` : undefined}
            className="h-10 bg-white pr-10 pl-9 font-mono"
            {...register('loadLb', {
              onChange: (event) => setValue('loadLb', event.target.value.replace(/[^\d,]/g, '')),
              onBlur: (event) => {
                const value = parseLoad(event.target.value)
                if (Number.isInteger(value) && value > 0) {
                  setValue('loadLb', value.toLocaleString('en-US'))
                }
              },
            })}
          />
          <span className="absolute top-1/2 right-3 -translate-y-1/2 text-sm text-muted-foreground">
            lb
          </span>
        </div>
        <FieldError id={`${ids.load}-error`} message={errors.loadLb?.message} />
        {!errors.loadLb && load > 30_000 && load <= MAX_LOAD_LB && (
          <StatusAlert tone="warning">
            {load > 40_000
              ? 'Heavy load: winds of 35–44 mph count as Severe; 45+ mph is No Travel.'
              : 'Loads over 30,000 lb: winds of 45+ mph are No Travel.'}
          </StatusAlert>
        )}
      </div>

      <Controller
        control={control}
        name="intervalMi"
        render={({ field }) => (
          <IntervalControl value={field.value} onChange={field.onChange} disabled={isLoading} />
        )}
      />

      <div className="space-y-2">
        {isLoading ? (
          <>
            <Button size="lg" className="h-10 w-full" disabled aria-live="polite">
              <Spinner /> Analyzing routes…
            </Button>
            <Button
              variant="link"
              className="w-full text-muted-foreground"
              onClick={() => dispatch(analysisCancelled())}
            >
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button type="submit" size="lg" className="h-10 w-full" disabled={blocked}>
              <Route aria-hidden className="size-4" /> Analyze routes
            </Button>
            {blocked && (
              <p role="status" className="text-center text-sm text-destructive">
                Fix {errorCount} {errorCount === 1 ? 'field' : 'fields'} to continue
              </p>
            )}
            {canClose && (
              <Button
                variant="link"
                className="w-full text-muted-foreground"
                onClick={() => dispatch(closeEditor())}
              >
                Back to results
              </Button>
            )}
          </>
        )}
      </div>
    </form>
  )
}
