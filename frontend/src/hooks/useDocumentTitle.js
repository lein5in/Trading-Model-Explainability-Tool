import { useEffect } from 'react'
import { APP_NAME } from '../config.js'

export function useDocumentTitle(title) {
  useEffect(() => {
    document.title = title ? `${APP_NAME}: ${title}` : APP_NAME
  }, [title])
}
