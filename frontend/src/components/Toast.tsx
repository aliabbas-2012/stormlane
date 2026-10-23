import { useEffect } from 'react'

const AUTO_DISMISS_MS = 8000

export function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, AUTO_DISMISS_MS)
    return () => window.clearTimeout(timer)
  }, [message, onDismiss])

  return (
    <div
      role="alert"
      className="fixed top-4 right-4 z-50 flex max-w-sm items-start gap-3 rounded-md border border-red-200 bg-white p-3 text-sm shadow-lg"
    >
      <span className="text-red-700">{message}</span>
      <button
        type="button"
        onClick={onDismiss}
        className="ml-auto text-gray-400 hover:text-gray-700"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  )
}
