const SECTION_TITLES = [
  'Executive Summary',
  'Behavior by Market Regime',
  'Dominant Factors',
  'Identified Risk Zones',
  'Limitations of this Analysis',
]

export function parseReportSections(reportText) {
  if (!reportText) {
    return []
  }

  const sections = []
  const lines = reportText.split('\n')
  let currentTitle = null
  let currentContent = []

  function flush() {
    if (currentTitle !== null) {
      sections.push({
        title: currentTitle,
        content: currentContent.join('\n').trim(),
      })
    }
  }

  for (const line of lines) {
    const trimmedLine = line.trim()
    const matchedTitle = SECTION_TITLES.find(
      (title) => trimmedLine === `${title}:` || trimmedLine === title
    )

    if (matchedTitle) {
      flush()
      currentTitle = matchedTitle
      currentContent = []
    } else if (currentTitle !== null) {
      currentContent.push(line)
    }
  }

  flush()

  if (sections.length === 0) {
    return [{ title: 'Report', content: reportText }]
  }

  return sections
}