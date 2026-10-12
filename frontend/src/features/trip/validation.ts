import { z } from 'zod'

import { addHours } from '@/lib/datetime'
import type { AnalyzeRequest } from '@/redux/types'

export const MAX_LOAD_LB = 80_000
/** Sent instead of a time when the departure field is left empty. */
export const DEPART_NOW = 'now'
/** Matches the backend's forecast window (14 days keeps Open-Meteo at one call per location). */
export const FORECAST_HORIZON_DAYS = 14
/** Small grace period so "now" doesn't fail while the user is typing. */
const PAST_GRACE_HOURS = 1
/**
 * Departure is local time at the origin, whose zone isn't known until the backend geocodes it.
 * The browser check allows the widest real-world offset difference; the backend checks exactly.
 */
export const ZONE_SLACK_HOURS = 14

const parseLoad = (value: string) => Number(value.replace(/,/g, ''))

/** Client-side checks for fast feedback. The backend re-validates everything. */
export const tripSchema = z
  .object({
    origin: z.string().trim().min(1, 'Enter an origin'),
    destination: z.string().trim().min(1, 'Enter a destination'),
    /**
     * <input type="datetime-local"> value: wall-clock time at the origin. Empty means "leave now",
     * which the backend resolves in the origin's zone (the browser's clock may be elsewhere).
     */
    departure: z
      .string()
      .refine(
        (value) => value === '' || !Number.isNaN(new Date(value).getTime()),
        'Choose a departure date and time',
      )
      .refine(
        (value) =>
          value === '' ||
          new Date(value) >= addHours(new Date(), -PAST_GRACE_HOURS - ZONE_SLACK_HOURS),
        'Departure is in the past',
      )
      .refine(
        (value) =>
          value === '' ||
          new Date(value) <= addHours(new Date(), FORECAST_HORIZON_DAYS * 24 + ZONE_SLACK_HOURS),
        `Forecasts cover the next ${FORECAST_HORIZON_DAYS} days — pick an earlier departure`,
      ),
    loadLb: z
      .string()
      .trim()
      .min(1, 'Enter the load weight')
      .refine(
        (value) => {
          const load = parseLoad(value)
          return Number.isInteger(load) && load >= 1 && load <= MAX_LOAD_LB
        },
        `Load must be between 1 and ${MAX_LOAD_LB.toLocaleString('en-US')} lb`,
      ),
    intervalMi: z.union([z.literal(10), z.literal(25), z.literal(50)]),
  })
  .refine((trip) => trip.origin.toLowerCase() !== trip.destination.toLowerCase(), {
    path: ['destination'],
    message: 'Destination must differ from origin',
  })

export type TripFormValues = z.infer<typeof tripSchema>
export type TripField = keyof TripFormValues
export type TripFormErrors = Partial<Record<TripField, string>>

export function toAnalyzeRequest(values: TripFormValues): AnalyzeRequest {
  return {
    origin: values.origin.trim(),
    destination: values.destination.trim(),
    departure_time: values.departure ? `${values.departure}:00` : DEPART_NOW,
    load_lb: parseLoad(values.loadLb),
    interval_mi: values.intervalMi,
  }
}

/** Maps DRF field names back to form fields so server errors show inline. */
const SERVER_FIELD_MAP: Record<string, TripField> = {
  origin: 'origin',
  destination: 'destination',
  departure_time: 'departure',
  load_lb: 'loadLb',
  interval_mi: 'intervalMi',
}

export function serverFieldErrors(
  fieldErrors: Record<string, string[]> | undefined,
): TripFormErrors {
  const errors: TripFormErrors = {}
  for (const [field, messages] of Object.entries(fieldErrors ?? {})) {
    const formField = SERVER_FIELD_MAP[field]
    if (formField && messages[0]) errors[formField] = messages[0]
  }
  return errors
}
