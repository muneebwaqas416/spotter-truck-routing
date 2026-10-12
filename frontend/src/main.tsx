import './index.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'

import { Toaster } from '@/components/ui/sonner'
import { store } from '@/redux/store'

import App from './App'

const root = document.getElementById('root')
if (!root) throw new Error('Root element #root not found')

createRoot(root).render(
  <StrictMode>
    <Provider store={store}>
      <App />
      {/* One toast at a time keeps feedback readable next to the map controls. */}
      <Toaster position="top-center" richColors visibleToasts={3} closeButton />
    </Provider>
  </StrictMode>,
)
