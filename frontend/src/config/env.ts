/**
 * Validated runtime configuration. Fails fast at startup instead of
 * surfacing as confusing network errors later.
 */
function requireEnv(name: string, value: string | undefined): string {
  if (!value) {
    throw new Error(`Missing required environment variable ${name}. See .env.example.`)
  }
  return value
}

export const env = {
  apiBaseUrl: requireEnv('VITE_API_BASE_URL', import.meta.env.VITE_API_BASE_URL).replace(
    /\/+$/,
    '',
  ),
  mapStyleUrl: requireEnv('VITE_MAP_STYLE_URL', import.meta.env.VITE_MAP_STYLE_URL),
} as const
