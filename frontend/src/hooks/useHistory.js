import { useSyncExternalStore } from 'react'
import { historyStore } from '../lib/history.js'

export function useHistory() {
  return useSyncExternalStore(historyStore.subscribe, historyStore.getSnapshot, historyStore.getSnapshot)
}
