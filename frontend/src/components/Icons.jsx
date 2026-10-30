function Svg({ size = 16, children, className, strokeWidth = 2, stroke = 'currentColor' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  )
}

export function LogoMark({ size = 26 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true">
      <rect x="1" y="1" width="24" height="24" rx="6" className="fill-ac" />
      <rect x="6" y="13" width="3" height="7" rx="1" className="fill-acf" />
      <rect x="11.5" y="8" width="3" height="12" rx="1" className="fill-acf" />
      <rect x="17" y="10.5" width="3" height="9.5" rx="1" className="fill-acf" />
    </svg>
  )
}

export function CheckIcon(props) {
  return (
    <Svg strokeWidth={2.4} {...props}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </Svg>
  )
}

export function WarningIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 3 2 20h20L12 3z" />
      <path d="M12 10v4M12 17.5v.01" />
    </Svg>
  )
}

export function AlertIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7.5v5.5M12 16.5v.01" />
    </Svg>
  )
}

export function LinkIcon(props) {
  return (
    <Svg {...props}>
      <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" />
      <path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />
    </Svg>
  )
}

export function UploadIcon(props) {
  return (
    <Svg strokeWidth={1.6} {...props}>
      <path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </Svg>
  )
}

export function CloseIcon(props) {
  return (
    <Svg {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  )
}
