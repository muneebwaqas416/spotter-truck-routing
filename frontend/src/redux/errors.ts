import type { FetchBaseQueryError } from '@reduxjs/toolkit/query'

/** Single error shape for every API call, so components never inspect raw fetch errors. */
export interface ApiError {
  /** HTTP status, or a client-side failure kind. */
  status: number | 'NETWORK_ERROR' | 'TIMEOUT_ERROR' | 'PARSING_ERROR'
  code?: string
  message: string
  /** DRF field validation errors, keyed by request field. */
  fieldErrors?: Record<string, string[]>
  /** From the Retry-After header on 429 responses. */
  retryAfterSeconds?: number
}

const STATUS_MESSAGES: Record<number, string> = {
  400: 'Some inputs are invalid.',
  429: 'Too many requests. Please wait a moment and try again.',
  502: 'An upstream service is unavailable. Please try again.',
  504: 'An upstream service timed out. Please try again.',
}

export function normalizeApiError(error: FetchBaseQueryError, headers?: Headers): ApiError {
  switch (error.status) {
    case 'FETCH_ERROR':
      return { status: 'NETWORK_ERROR', message: 'Cannot reach the server. Check your connection.' }
    case 'TIMEOUT_ERROR':
      return { status: 'TIMEOUT_ERROR', message: 'The request took too long. Please try again.' }
    case 'PARSING_ERROR':
      return { status: 'PARSING_ERROR', message: 'The server returned an unexpected response.' }
    case 'CUSTOM_ERROR':
      return { status: 'NETWORK_ERROR', message: error.error }
  }

  const body = isRecord(error.data) ? error.data : {}
  const detail = typeof body.detail === 'string' ? body.detail : undefined
  const code = typeof body.code === 'string' ? body.code : undefined
  const fieldErrors = error.status === 400 ? extractFieldErrors(body) : undefined
  const retryAfterSeconds = parseRetryAfter(headers?.get('Retry-After'))

  return {
    status: error.status,
    code,
    message: detail ?? STATUS_MESSAGES[error.status] ?? `Request failed (${error.status}).`,
    ...(fieldErrors && { fieldErrors }),
    ...(retryAfterSeconds !== undefined && { retryAfterSeconds }),
  }
}

function parseRetryAfter(value: string | null | undefined): number | undefined {
  if (!value) return undefined
  const seconds = Number(value)
  return Number.isFinite(seconds) && seconds >= 0 ? Math.ceil(seconds) : undefined
}

function extractFieldErrors(body: Record<string, unknown>): Record<string, string[]> | undefined {
  const entries = Object.entries(body).filter(
    (entry): entry is [string, string[]] =>
      Array.isArray(entry[1]) && entry[1].every((message) => typeof message === 'string'),
  )
  return entries.length > 0 ? Object.fromEntries(entries) : undefined
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
