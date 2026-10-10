import type { RiskLevel } from '@/redux/types'

/** Display-only metadata for risk levels. Classification happens on the backend. */
export const RISK_STYLES: Record<RiskLevel, { label: string; color: string; rgb: RGB }> = {
  LOW: { label: 'Low', color: '#16a34a', rgb: [22, 163, 74] },
  MODERATE: { label: 'Moderate', color: '#eab308', rgb: [234, 179, 8] },
  HIGH: { label: 'High', color: '#f97316', rgb: [249, 115, 22] },
  SEVERE: { label: 'Severe', color: '#dc2626', rgb: [220, 38, 38] },
  NO_TRAVEL: { label: 'No Travel', color: '#4c1d95', rgb: [76, 29, 149] },
  UNKNOWN: { label: 'Unknown', color: '#9ca3af', rgb: [156, 163, 175] },
}

type RGB = [number, number, number]

/** Worst-last ordering used for stacked bars and legends. */
export const RISK_ORDER: RiskLevel[] = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'NO_TRAVEL', 'UNKNOWN']

/** Legend copy, mirroring the backend thresholds in CLAUDE.md §3. */
export const RISK_RULES: Record<RiskLevel, string> = {
  LOW: 'Wind < 25 mph · rain < 0.10 · snow < 0.5 in/hr',
  MODERATE: 'Wind 25–34 · rain 0.10–0.25 · snow 0.5–1.0',
  HIGH: 'Wind 35–44 · rain 0.25–0.50 · snow 1.0–2.0',
  SEVERE: 'Wind 45–54 · rain 0.50–1.00 · snow 2.0–3.0',
  NO_TRAVEL: 'Wind ≥ 55 · rain > 1.00 · snow > 3.0',
  UNKNOWN: 'Forecast unavailable',
}

/** Heatmap color ramp over risk scores 0 (Low) → 4 (No Travel). */
export const HEATMAP_COLOR_RANGE: RGB[] = [
  RISK_STYLES.LOW.rgb,
  RISK_STYLES.MODERATE.rgb,
  RISK_STYLES.HIGH.rgb,
  RISK_STYLES.SEVERE.rgb,
  RISK_STYLES.NO_TRAVEL.rgb,
]
