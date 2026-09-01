const SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'features', label: 'Features' },
  { id: 'trades', label: 'Trades' },
  { id: 'report', label: 'Report' },
]

function Sidebar({ activeSection, onSectionChange, onSignOut }) {
  return (
    <aside className="w-48 shrink-0 border-r border-neutral-800 bg-neutral-950 flex flex-col h-screen sticky top-0">
      <div className="px-4 py-5 border-b border-neutral-800">
        <span className="text-sm font-bold tracking-widest text-neutral-100">TME</span>
      </div>

      <nav className="flex-1 py-4">
        <button
          type="button"
          onClick={() => onSectionChange('new-analysis')}
          className={`w-full text-left px-4 py-2 text-xs uppercase tracking-wider transition-colors ${
            activeSection === 'new-analysis'
              ? 'text-neutral-100 bg-neutral-900'
              : 'text-neutral-500 hover:text-neutral-300'
          }`}
        >
          New Analysis
        </button>
        <button
          type="button"
          disabled
          className="w-full text-left px-4 py-2 text-xs uppercase tracking-wider text-neutral-700 cursor-not-allowed"
        >
          History
        </button>

        <div className="mt-4 border-t border-neutral-800 pt-4">
          {SECTIONS.map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => onSectionChange(section.id)}
              className={`w-full text-left px-4 py-2 text-xs uppercase tracking-wider transition-colors ${
                activeSection === section.id
                  ? 'text-neutral-100 bg-neutral-900 border-l-2 border-green-500'
                  : 'text-neutral-500 hover:text-neutral-300'
              }`}
            >
              {section.label}
            </button>
          ))}
        </div>
      </nav>

      <div className="px-4 py-4 border-t border-neutral-800">
        <button
          type="button"
          onClick={onSignOut}
          className="text-xs text-neutral-600 hover:text-neutral-400 transition-colors"
        >
          Sign out
        </button>
      </div>
    </aside>
  )
}

export default Sidebar