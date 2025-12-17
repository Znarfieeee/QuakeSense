import { useState } from 'react'
import Dashboard from './components/Dashboard'
import AITraining from './components/AITraining'
import { Activity, Brain } from 'lucide-react'

function App() {
  const [activeView, setActiveView] = useState('dashboard') // 'dashboard' or 'training'

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Navigation Bar */}
      <nav className="bg-slate-800 border-b border-slate-700">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-6 h-6 text-orange-500" />
              <span className="text-xl font-bold text-white">QuakeSense</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setActiveView('dashboard')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
                  activeView === 'dashboard'
                    ? 'bg-orange-500 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <Activity className="w-4 h-4" />
                Dashboard
              </button>
              <button
                onClick={() => setActiveView('training')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 ${
                  activeView === 'training'
                    ? 'bg-purple-500 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <Brain className="w-4 h-4" />
                AI Training
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      {activeView === 'dashboard' ? <Dashboard /> : <AITraining />}
    </div>
  )
}

export default App
