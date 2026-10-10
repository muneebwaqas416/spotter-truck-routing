import { configureStore } from '@reduxjs/toolkit'

import { api } from '@/redux/api'
import { tripReducer } from '@/features/trip/tripSlice'

export function makeStore() {
  return configureStore({
    reducer: {
      [api.reducerPath]: api.reducer,
      trip: tripReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware().concat(api.middleware),
  })
}

export const store = makeStore()

export type AppStore = ReturnType<typeof makeStore>
export type RootState = ReturnType<AppStore['getState']>
export type AppDispatch = AppStore['dispatch']
