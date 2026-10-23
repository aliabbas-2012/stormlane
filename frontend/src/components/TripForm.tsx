import { useState } from 'react'

import { dateTimeLocalToIso, defaultDeparture } from '../lib/format'
import type { AnalyzeRequest, IntervalMiles, Place } from '../types/api'
import { LocationInput } from './LocationInput'

const INTERVALS: IntervalMiles[] = [10, 25, 50]
const MAX_LOAD_LBS = 200_000
const DEPARTURE_GRACE_MS = 15 * 60 * 1000

const EXAMPLE_TRIP = {
  origin: { label: 'Dallas, Texas', lat: 32.7767, lon: -96.797 },
  destination: { label: 'Denver, Colorado', lat: 39.7392, lon: -104.9903 },
  loadLbs: 38_000,
} as const

interface Props {
  isPending: boolean
  showExample: boolean
  onSubmit: (request: AnalyzeRequest) => void
}

type Errors = Partial<Record<'origin' | 'destination' | 'departure' | 'load', string>>

export function TripForm({ isPending, showExample, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [departure, setDeparture] = useState(defaultDeparture)
  const [load, setLoad] = useState('38000')
  const [interval, setIntervalMiles] = useState<IntervalMiles>(25)
  const [errors, setErrors] = useState<Errors>({})

  function validate(): Errors {
    const next: Errors = {}
    if (!origin) next.origin = 'Choose an origin from the suggestions.'
    if (!destination) next.destination = 'Choose a destination from the suggestions.'
    const departureMs = new Date(departure).getTime()
    if (Number.isNaN(departureMs)) next.departure = 'Enter a departure date and time.'
    else if (departureMs < Date.now() - DEPARTURE_GRACE_MS)
      next.departure = 'Departure is in the past.'
    const loadLbs = Number(load)
    if (!Number.isFinite(loadLbs) || loadLbs < 1 || loadLbs > MAX_LOAD_LBS)
      next.load = `Enter a load between 1 and ${MAX_LOAD_LBS.toLocaleString()} lb.`
    return next
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const next = validate()
    setErrors(next)
    if (Object.keys(next).length || !origin || !destination) return
    onSubmit({
      origin,
      destination,
      departure_time: dateTimeLocalToIso(departure),
      load_lbs: Number(load),
      interval_miles: interval,
    })
  }

  function runExample() {
    const fresh = defaultDeparture()
    setOrigin(EXAMPLE_TRIP.origin)
    setDestination(EXAMPLE_TRIP.destination)
    setDeparture(fresh)
    setLoad(String(EXAMPLE_TRIP.loadLbs))
    setErrors({})
    onSubmit({
      origin: EXAMPLE_TRIP.origin,
      destination: EXAMPLE_TRIP.destination,
      departure_time: dateTimeLocalToIso(fresh),
      load_lbs: EXAMPLE_TRIP.loadLbs,
      interval_miles: interval,
    })
  }

  const loadNumber = Number(load)

  return (
    <form onSubmit={submit} className="space-y-3" noValidate>
      <LocationInput
        label="Origin"
        placeholder="City or address"
        value={origin}
        onChange={setOrigin}
        error={errors.origin}
      />
      <LocationInput
        label="Destination"
        placeholder="City or address"
        value={destination}
        onChange={setDestination}
        error={errors.destination}
      />

      <div className="grid grid-cols-5 gap-3">
        <div className="col-span-3">
          <label htmlFor="departure" className="block text-xs font-medium text-gray-700">
            Departure (local time)
          </label>
          <input
            id="departure"
            type="datetime-local"
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-2 text-sm shadow-sm focus:ring-2 focus:ring-sky-500 focus:outline-none"
            value={departure}
            onChange={(event) => setDeparture(event.target.value)}
            aria-invalid={Boolean(errors.departure)}
          />
          {errors.departure && <p className="mt-1 text-xs text-red-600">{errors.departure}</p>}
        </div>
        <div className="col-span-2">
          <label htmlFor="load" className="block text-xs font-medium text-gray-700">
            Load weight (lb)
          </label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            min={1}
            max={MAX_LOAD_LBS}
            step={500}
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-sky-500 focus:outline-none"
            value={load}
            onChange={(event) => setLoad(event.target.value)}
            aria-invalid={Boolean(errors.load)}
            aria-describedby="load-hint"
          />
          {errors.load ? (
            <p className="mt-1 text-xs text-red-600">{errors.load}</p>
          ) : (
            <p id="load-hint" className="mt-1 text-[11px] leading-tight text-gray-500">
              {loadNumber > 80_000
                ? 'Above the 80,000 lb US gross limit: permit load.'
                : "Typical loaded 53' trailer: 35,000–45,000 lb"}
            </p>
          )}
        </div>
      </div>

      <fieldset>
        <legend className="text-xs font-medium text-gray-700">Checkpoint every</legend>
        <div className="mt-1 grid grid-cols-3 rounded-md border border-gray-300 p-0.5 text-sm">
          {INTERVALS.map((value) => (
            <label
              key={value}
              className={`cursor-pointer rounded px-2 py-1.5 text-center has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-sky-500 ${
                interval === value
                  ? 'bg-sky-600 font-medium text-white'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
            >
              <input
                type="radio"
                name="interval"
                className="sr-only"
                checked={interval === value}
                onChange={() => setIntervalMiles(value)}
              />
              {value} mi
            </label>
          ))}
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={isPending}
        className="flex w-full items-center justify-center gap-2 rounded-md bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-sky-700 disabled:cursor-wait disabled:opacity-70"
      >
        {isPending && (
          <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
        )}
        {isPending ? 'Analyzing routes & weather…' : 'Analyze routes'}
      </button>

      {showExample && (
        <button
          type="button"
          onClick={runExample}
          disabled={isPending}
          className="w-full rounded-md border border-dashed border-gray-300 px-4 py-2 text-sm text-gray-600 hover:border-sky-400 hover:text-sky-700 disabled:opacity-50"
        >
          Try an example: Dallas, TX → Denver, CO
        </button>
      )}
    </form>
  )
}
