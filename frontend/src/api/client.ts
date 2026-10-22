const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/** Mirrors the backend's uniform error body: {error: {code, message}}. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError('network_error', 'Could not reach the StormLane API.', 0)
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error
    throw new ApiError(
      error?.code ?? 'http_error',
      error?.message ?? `Request failed (${response.status})`,
      response.status,
    )
  }
  return body as T
}
