import { formatTime } from '../lib/format'
import { HEATMAP_HOURS, METRIC_CAPTIONS } from '../lib/heatmap'
import type { HeatmapMetric } from '../types/api'

const METRICS: { value: HeatmapMetric; label: string }[] = [
  { value: 'risk', label: 'Risk' },
  { value: 'wind', label: 'Wind' },
  { value: 'rain', label: 'Rain' },
  { value: 'snow', label: 'Snow' },
]

interface Props {
  hours: string[]
  hour: number
  onHour: (hour: number) => void
  playing: boolean
  onTogglePlay: () => void
  metric: HeatmapMetric
  onMetric: (metric: HeatmapMetric) => void
  visible: boolean
  onVisible: (visible: boolean) => void
  status: 'loading' | 'error' | 'ready'
}

export function TimeSlider(props: Props) {
  const {
    hours,
    hour,
    onHour,
    playing,
    onTogglePlay,
    metric,
    onMetric,
    visible,
    onVisible,
    status,
  } = props
  const ready = status === 'ready'
  return (
    <div className="w-[min(560px,calc(100vw-24px))] rounded-lg bg-white/95 p-3 text-xs shadow-lg backdrop-blur">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onTogglePlay}
          disabled={!ready}
          aria-label={playing ? 'Pause forecast animation' : 'Play forecast animation'}
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-40"
        >
          {/* SVG rather than ▶/❚❚ glyphs, which some platforms render as colour emoji. */}
          <svg viewBox="0 0 16 16" className="size-3.5" fill="currentColor" aria-hidden="true">
            {playing ? (
              <path d="M4 2h3v12H4zM9 2h3v12H9z" />
            ) : (
              <path d="M4 2.5v11a.5.5 0 0 0 .77.42l8.5-5.5a.5.5 0 0 0 0-.84l-8.5-5.5A.5.5 0 0 0 4 2.5z" />
            )}
          </svg>
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between">
            <span className="font-semibold text-gray-900 tabular-nums">
              +{hour}h · {hours[hour] ? formatTime(hours[hour]) : '…'}
            </span>
            <span className="text-gray-500">
              {status === 'loading'
                ? 'Loading weather heatmap…'
                : status === 'error'
                  ? 'Heatmap unavailable'
                  : '0–48 h forecast'}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={HEATMAP_HOURS - 1}
            step={1}
            value={hour}
            onChange={(event) => onHour(Number(event.target.value))}
            aria-label="Forecast hour"
            aria-valuetext={
              hours[hour] ? `+${hour} hours, ${formatTime(hours[hour])}` : `+${hour} hours`
            }
            className="mt-1 w-full accent-sky-600"
          />
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <div
          className="flex rounded-md border border-gray-300 p-0.5"
          role="radiogroup"
          aria-label="Heatmap metric"
        >
          {METRICS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={metric === value}
              onClick={() => onMetric(value)}
              className={`rounded px-2 py-0.5 ${metric === value ? 'bg-sky-600 text-white' : 'text-gray-700 hover:bg-gray-100'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1 text-gray-700">
          <input
            type="checkbox"
            checked={visible}
            onChange={(event) => onVisible(event.target.checked)}
          />
          Heatmap
        </label>
        <span className="ml-auto text-gray-500">{METRIC_CAPTIONS[metric]}</span>
      </div>
    </div>
  )
}
