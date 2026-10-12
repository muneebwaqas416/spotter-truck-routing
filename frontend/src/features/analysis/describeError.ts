import type { ApiError } from '@/redux/errors'

export type ErrorTone = 'danger' | 'warning' | 'info'

export interface ErrorDescription {
  title: string
  body: string
  tone: ErrorTone
  /** Whether retrying the same request can succeed. */
  retryable: boolean
}

/** Turns a normalized API error into copy for alerts. Unknown risk is never presented as safe. */
export function describeError(error: ApiError): ErrorDescription {
  if (error.status === 'NETWORK_ERROR') {
    return {
      title: "Can't reach the server",
      body: 'Check your connection and try again.',
      tone: 'info',
      retryable: true,
    }
  }
  if (error.status === 'TIMEOUT_ERROR' || error.status === 504) {
    return {
      title: 'Request timed out',
      body: 'A routing or weather service took too long. Routes were not scored.',
      tone: 'warning',
      retryable: true,
    }
  }
  if (error.status === 429) {
    return {
      title: 'Too many requests',
      body: 'Please wait before analyzing again.',
      tone: 'warning',
      retryable: true,
    }
  }
  if (error.status === 503) {
    return {
      title: 'Service is busy',
      body: `${error.message} Routes were not scored, and nothing is assumed safe.`,
      tone: 'warning',
      retryable: true,
    }
  }
  if (error.code === 'no_route') {
    return {
      title: 'No truck route found',
      body: 'No truck route was found between these places. Try nearby cities.',
      tone: 'warning',
      retryable: false,
    }
  }
  if (error.code === 'place_not_found') {
    return {
      title: 'Place not found',
      body: error.message || 'Pick a place from the suggestions.',
      tone: 'danger',
      retryable: false,
    }
  }
  if (error.status === 400) {
    return {
      title: 'Check the trip details',
      body: 'Some fields need attention.',
      tone: 'danger',
      retryable: false,
    }
  }
  if (error.status === 502) {
    return {
      title: 'Weather or routing service unavailable',
      body: `${error.message} Routes were not scored, and nothing is assumed safe.`,
      tone: 'danger',
      retryable: true,
    }
  }
  return {
    title: 'Something went wrong',
    body: error.message,
    tone: 'danger',
    retryable: true,
  }
}
