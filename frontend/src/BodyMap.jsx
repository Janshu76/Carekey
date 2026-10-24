import { useMemo } from 'react'

const regions = [
  { id: 'head', label: 'Head', x: 140, y: 56 },
  { id: 'chest', label: 'Chest', x: 140, y: 160 },
  { id: 'abdomen', label: 'Abdomen', x: 140, y: 240 },
  { id: 'left_arm', label: 'Left arm', x: 67, y: 224 },
  { id: 'right_arm', label: 'Right arm', x: 213, y: 224 },
  { id: 'left_knee', label: 'Left knee', x: 114, y: 382 },
  { id: 'right_knee', label: 'Right knee', x: 166, y: 382 },
  { id: 'left_leg', label: 'Left leg', x: 112, y: 443 },
  { id: 'right_leg', label: 'Right leg', x: 168, y: 443 },
]

function regionFor(condition) {
  const value = (condition.body_region || '').toLowerCase()
  if (value !== 'whole_body') {
    const matched = regions.find((region) => value.includes(region.id))
    if (matched) return matched.id
  }
  const text = `${condition.name} ${condition.notes || ''}`.toLowerCase()
  if (/head|brain|migraine|stroke/.test(text)) return 'head'
  if (/heart|chest|lung|asthma/.test(text)) return 'chest'
  if (/kidney|diabetes|stomach|abdomen/.test(text)) return 'abdomen'
  if (/shoulder|arm|wrist/.test(text)) return 'left_arm'
  return 'chest'
}

export default function BodyMap({ conditions = [], selectedId, onSelect }) {
  const markers = useMemo(
    () =>
      conditions.map((condition) => ({
        condition,
        region: regionFor(condition),
      })),
    [conditions],
  )

  return (
    <div className="body-map" aria-label="Interactive body map">
      <div className="body-map-art">
        <svg viewBox="0 0 280 500" role="img" aria-labelledby="body-map-title">
          <title id="body-map-title">Front view body map with selectable health markers</title>
          <defs>
            <linearGradient id="body-fill" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0%" stopColor="#dbeaff" />
              <stop offset="50%" stopColor="#f6faff" />
              <stop offset="100%" stopColor="#c8ddfb" />
            </linearGradient>
            <linearGradient id="body-shadow" x1="0" x2="1">
              <stop offset="0%" stopColor="#b5cff2" stopOpacity=".75" />
              <stop offset="50%" stopColor="#fff" stopOpacity=".2" />
              <stop offset="100%" stopColor="#b5cff2" stopOpacity=".75" />
            </linearGradient>
          </defs>
          <g className="body-silhouette">
            <path
              className="body-shape"
              d="M122 32c0-18 8-27 18-27s18 9 18 27c0 13-4 22-10 28l5 15 26 12c16 7 25 22 29 39l18 74c3 13-4 23-15 25-9 2-16-4-19-13l-18-50-2 74 12 42-9 28-9 94c-1 11-8 18-17 18s-15-7-15-18l-4-77-4 77c0 11-6 18-15 18s-16-7-17-18l-9-94-9-28 12-42-2-74-18 50c-3 9-10 15-19 13-11-2-18-12-15-25l18-74c4-17 13-32 29-39l26-12 5-15c-6-6-10-15-10-28Z"
            />
            <path
              className="body-highlight"
              d="M122 32c0-18 8-27 18-27s18 9 18 27c0 13-4 22-10 28l5 15 26 12c16 7 25 22 29 39l18 74c3 13-4 23-15 25-9 2-16-4-19-13l-18-50-2 74 12 42-9 28-9 94c-1 11-8 18-17 18s-15-7-15-18l-4-77-4 77c0 11-6 18-15 18s-16-7-17-18l-9-94-9-28 12-42-2-74-18 50c-3 9-10 15-19 13-11-2-18-12-15-25l18-74c4-17 13-32 29-39l26-12 5-15c-6-6-10-15-10-28Z"
            />
            <path className="body-line" d="M140 67v35m-33 3 33 7 33-7m-45 7c-7 27-5 51 12 66 17-15 19-39 12-66m-12 0v85m-24 30h48m-43 26 19 14 19-14m-20-58v58m-30 153h62m-54 39h45" />
            <path className="body-line" d="m97 137-21 85m107-85 21 85M116 300l-4 43m52-43 4 43m-38 10v61m20-61v61" />
          </g>
          {regions.map((region) => {
            const matches = markers.filter((marker) => marker.region === region.id)
            if (!matches.length) return null
            const active = matches.some(({ condition }) => condition.id === selectedId)
            return (
              <g
                key={region.id}
                className={`body-marker ${matches.every(({ condition }) => !condition.is_active) ? 'is-history' : ''} ${active ? 'is-selected' : ''}`}
                role="button"
                tabIndex="0"
                aria-label={`${region.label}: ${matches.length} record${matches.length > 1 ? 's' : ''}`}
                onClick={() => onSelect?.(matches[0].condition)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onSelect?.(matches[0].condition)
                  }
                }}
              >
                <circle cx={region.x} cy={region.y} r="13" className="marker-ring" />
                <circle cx={region.x} cy={region.y} r="8" className="marker-dot" />
                {matches.length > 1 && (
                  <text x={region.x + 12} y={region.y - 10} className="marker-count">
                    {matches.length}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
        {!conditions.length && (
          <div className="body-empty-note">
            <span className="marker-dot-small" />
            Add a record to place it on the body map
          </div>
        )}
      </div>
      <div className="body-map-legend">
        <span><i className="legend-dot active" /> Current</span>
        <span><i className="legend-dot history" /> History</span>
        <span className="map-hint">Tap a marker to view</span>
      </div>
    </div>
  )
}
