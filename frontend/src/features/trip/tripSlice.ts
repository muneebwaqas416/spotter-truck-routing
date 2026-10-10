import { createSlice, type PayloadAction } from '@reduxjs/toolkit'

import type { AnalyzeRequest } from '@/redux/types'

export interface SelectedCheckpoint {
  routeId: string
  index: number
}

export interface TripState {
  /** The submitted analysis request; drives the cached analyzeRoutes query. */
  request: AnalyzeRequest | null
  /** Epoch ms of the last submit, used to tell fresh results from cached ones. */
  submittedAt: number | null
  isEditing: boolean
  selectedRouteId: string | null
  selectedCheckpoint: SelectedCheckpoint | null
  heatmapEnabled: boolean
  /** Hour offset 0–48 shown by the heatmap slider. */
  forecastHour: number
  legendOpen: boolean
}

const initialState: TripState = {
  request: null,
  submittedAt: null,
  isEditing: true,
  selectedRouteId: null,
  selectedCheckpoint: null,
  heatmapEnabled: true,
  forecastHour: 0,
  legendOpen: true,
}

export const MAX_FORECAST_HOUR = 48

const tripSlice = createSlice({
  name: 'trip',
  initialState,
  reducers: {
    analysisSubmitted: {
      reducer(state, action: PayloadAction<{ request: AnalyzeRequest; at: number }>) {
        state.request = action.payload.request
        state.submittedAt = action.payload.at
        state.isEditing = false
        state.selectedRouteId = null
        state.selectedCheckpoint = null
        state.forecastHour = 0
      },
      // Timestamp here so components stay pure; used to tell fresh results from cached ones.
      prepare: (request: AnalyzeRequest) => ({ payload: { request, at: Date.now() } }),
    },
    analysisCancelled(state) {
      state.request = null
      state.submittedAt = null
      state.isEditing = true
    },
    editTrip(state) {
      state.isEditing = true
    },
    closeEditor(state) {
      state.isEditing = false
    },
    routeSelected(state, action: PayloadAction<string>) {
      state.selectedRouteId = action.payload
      state.selectedCheckpoint = null
    },
    checkpointSelected(state, action: PayloadAction<SelectedCheckpoint | null>) {
      state.selectedCheckpoint = action.payload
      if (action.payload) state.selectedRouteId = action.payload.routeId
    },
    heatmapEnabledChanged(state, action: PayloadAction<boolean>) {
      state.heatmapEnabled = action.payload
    },
    forecastHourChanged(state, action: PayloadAction<number>) {
      state.forecastHour = Math.min(MAX_FORECAST_HOUR, Math.max(0, Math.round(action.payload)))
    },
    legendToggled(state) {
      state.legendOpen = !state.legendOpen
    },
  },
})

export const {
  analysisSubmitted,
  analysisCancelled,
  editTrip,
  closeEditor,
  routeSelected,
  checkpointSelected,
  heatmapEnabledChanged,
  forecastHourChanged,
  legendToggled,
} = tripSlice.actions

export const tripReducer = tripSlice.reducer
