import { useId, useState } from 'react'

import { useGeocode } from '../api/hooks'
import type { Place } from '../types/api'

interface Props {
  label: string
  placeholder: string
  value: Place | null
  onChange: (place: Place | null) => void
  error?: string
}

/** Autocomplete combobox (WAI-ARIA pattern). Typing clears the chosen place until the user
 * picks a suggestion, so the form can never submit text that was not geocoded. */
export function LocationInput({ label, placeholder, value, onChange, error }: Props) {
  const id = useId()
  // null = not editing: show the selected place's label.
  const [draft, setDraft] = useState<string | null>(null)
  const [focused, setFocused] = useState(false)
  const [highlight, setHighlight] = useState(0)

  const text = draft ?? value?.label ?? ''
  const searching = draft !== null
  const { data: places = [], isFetching, isError } = useGeocode(text, searching)
  const open = focused && searching && text.trim().length >= 2

  function select(place: Place) {
    onChange(place)
    setDraft(null)
    setHighlight(0)
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || places.length === 0) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      setHighlight((h) => (h + step + places.length) % places.length)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      select(places[Math.min(highlight, places.length - 1)])
    } else if (event.key === 'Escape') {
      setDraft(null)
    }
  }

  return (
    <div className="relative">
      <label htmlFor={id} className="block text-xs font-medium text-gray-700">
        {label}
      </label>
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        aria-activedescendant={open && places.length ? `${id}-opt-${highlight}` : undefined}
        aria-invalid={Boolean(error)}
        autoComplete="off"
        className={`mt-1 w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-sky-500 focus:outline-none ${
          error ? 'border-red-400' : 'border-gray-300'
        }`}
        placeholder={placeholder}
        value={text}
        onChange={(event) => {
          setDraft(event.target.value)
          setHighlight(0)
          if (value) onChange(null)
        }}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onKeyDown={onKeyDown}
      />
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
      {open && (
        <ul
          id={`${id}-list`}
          role="listbox"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-gray-200 bg-white py-1 text-sm shadow-lg"
        >
          {places.map((place, index) => (
            <li
              key={`${place.label}-${place.lat}-${place.lon}`}
              id={`${id}-opt-${index}`}
              role="option"
              aria-selected={index === highlight}
              className={`cursor-pointer px-3 py-2 ${index === highlight ? 'bg-sky-50' : ''}`}
              // mousedown, not click: it fires before the input's blur closes the list.
              onMouseDown={(event) => {
                event.preventDefault()
                select(place)
              }}
              onMouseEnter={() => setHighlight(index)}
            >
              {place.label}
            </li>
          ))}
          {places.length === 0 && (
            <li className="px-3 py-2 text-gray-500">
              {isError ? 'Search unavailable' : isFetching ? 'Searching…' : 'No matches'}
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
