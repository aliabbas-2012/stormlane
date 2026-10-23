import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'

import { useDebouncedValue } from '../lib/useDebouncedValue'
import type { Analysis, AnalyzeRequest, Place } from '../types/api'
import { apiFetch } from './client'

const GEOCODE_DEBOUNCE_MS = 300
const GEOCODE_MIN_CHARS = 2

/** Fired on load so a sleeping backend starts waking before the user submits a trip. */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<{ status: string }>('/api/health'),
    staleTime: Infinity,
    retry: 2,
  })
}

export function useGeocode(query: string, enabled: boolean) {
  const debounced = useDebouncedValue(query.trim(), GEOCODE_DEBOUNCE_MS)
  return useQuery({
    queryKey: ['geocode', debounced.toLowerCase()],
    queryFn: ({ signal }) =>
      apiFetch<Place[]>(`/api/geocode?q=${encodeURIComponent(debounced)}`, { signal }),
    enabled: enabled && debounced.length >= GEOCODE_MIN_CHARS,
    staleTime: 60 * 60 * 1000,
    // Keep showing the last suggestions while the next keystroke's results load.
    placeholderData: keepPreviousData,
    retry: false,
  })
}

export function useAnalyze() {
  return useMutation({
    mutationFn: (body: AnalyzeRequest) =>
      apiFetch<Analysis>('/api/analyze', { method: 'POST', body: JSON.stringify(body) }),
  })
}
