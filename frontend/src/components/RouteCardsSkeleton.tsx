export function RouteCardsSkeleton() {
  return (
    <ul className="space-y-2" aria-label="Loading routes">
      {[0, 1, 2].map((i) => (
        <li key={i} className="animate-pulse rounded-lg border border-gray-200 bg-white p-3">
          <div className="h-4 w-24 rounded bg-gray-200" />
          <div className="mt-2 h-3 w-48 rounded bg-gray-100" />
          <div className="mt-3 h-2.5 w-full rounded-full bg-gray-100" />
          <div className="mt-3 grid grid-cols-4 gap-2">
            {[0, 1, 2, 3].map((j) => (
              <div key={j} className="h-6 rounded bg-gray-100" />
            ))}
          </div>
        </li>
      ))}
    </ul>
  )
}
