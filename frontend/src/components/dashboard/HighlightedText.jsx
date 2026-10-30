import { useMemo } from 'react'
import { highlightNumbers } from '../../lib/highlight.js'

export default function HighlightedText({ text, unverified, className = '' }) {
  const segments = useMemo(() => highlightNumbers(text, unverified), [text, unverified])
  const paragraphs = useMemo(() => {
    const result = [[]]
    segments.forEach((segment, index) => {
      if (segment.type !== 'text' || !segment.text.includes('\n\n')) {
        result[result.length - 1].push({ ...segment, key: index })
        return
      }
      segment.text.split(/\n{2,}/).forEach((part, partIndex) => {
        if (partIndex > 0) result.push([])
        if (part) result[result.length - 1].push({ type: 'text', text: part, key: `${index}-${partIndex}` })
      })
    })
    return result.filter((paragraph) => paragraph.length)
  }, [segments])

  return paragraphs.map((paragraph, index) => (
    <p key={index} className={`m-0 ${className}`}>
      {paragraph.map((segment) => {
        if (segment.type === 'verified') {
          return (
            <span key={segment.key} className="num" title="Matched to the computed data">
              {segment.text}
            </span>
          )
        }
        if (segment.type === 'unverified') {
          return (
            <mark key={segment.key} className="flag text-tx" title="Not found in the computed data">
              {segment.text}
            </mark>
          )
        }
        return <span key={segment.key}>{segment.text}</span>
      })}
    </p>
  ))
}
