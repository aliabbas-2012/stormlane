import { useQuery } from '@tanstack/react-query'

import { apiFetch } from './client'

/** Fired on load so a sleeping backend starts waking before the user submits a trip. */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch<{ status: string }>('/api/health'),
    staleTime: Infinity,
    retry: 2,
  })
}
