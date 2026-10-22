import { useHealth } from './api/hooks'
import { MapView } from './components/MapView'

export default function App() {
  const health = useHealth()

  return (
    <div className="flex h-full flex-col md:flex-row">
      <aside className="order-2 w-full shrink-0 overflow-y-auto border-gray-200 bg-white p-4 md:order-1 md:w-[380px] md:border-r">
        <h1 className="text-xl font-semibold text-gray-900">StormLane</h1>
        <p className="mt-1 text-sm text-gray-600">Weather-aware truck routing</p>
        <p className="mt-4 text-xs text-gray-500">
          API: {health.isPending ? 'connecting…' : health.isError ? 'unreachable' : 'connected'}
        </p>
      </aside>
      <main className="order-1 min-h-[50vh] flex-1 md:order-2">
        <MapView />
      </main>
    </div>
  )
}
