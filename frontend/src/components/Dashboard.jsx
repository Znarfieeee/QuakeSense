import { useState, useEffect } from 'react';
import EarthquakeAlerts from './EarthquakeAlerts';
import EarthquakeStats from './EarthquakeStats';
import FrequencyChart from './FrequencyChart';
import EarthquakeTable from './EarthquakeTable';
import { AlertTriangle, Activity, Shield, TrendingUp } from 'lucide-react';

// Backend API configuration
const API_BASE_URL = 'http://192.168.1.31:5000/api';

export default function Dashboard() {
  const [earthquakeData, setEarthquakeData] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    today: 0,
    falseAlarms: 0,
    accuracy: 0
  });
  const [activeAlert, setActiveAlert] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Fetch earthquake data from backend
  const fetchEarthquakeData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/events?limit=50`);
      if (response.ok) {
        const data = await response.json();
        console.log('📊 Fetched data from backend:', data);
        setIsConnected(true);

        // Transform backend data to frontend format
        // Backend auto-deletes oldest data (maxlen=100), so we always get latest events
        const transformedData = data.events.map((event, index) => {
          // Use server_timestamp (ISO format) for display, not ESP32 millis timestamp
          const timestamp = event.server_timestamp;
          const confidence = event.ai_confidence ? (event.ai_confidence * 100).toFixed(1) : '50.0';

          return {
            id: index,
            timestamp: timestamp,
            magnitude: parseFloat(event.horizontal_accel) || 0,
            location: event.device_id || 'Unknown Device',
            falseAlarm: event.ai_classification === 'false_alarm',
            confidence: confidence,
            totalAccel: event.total_accel || 0,
            soundLevel: event.sound_level || 0,
            soundCorrelated: event.sound_correlated || false,
            aiReasoning: event.ai_reasoning || 'No reasoning provided',
            // Keep raw data for debugging
            rawData: event
          };
        });

        console.log('✨ Transformed data:', transformedData);
        setEarthquakeData(transformedData);
        setLastUpdate(new Date());

        // Calculate stats
        const today = new Date().toDateString();
        const todayQuakes = transformedData.filter(q =>
          new Date(q.timestamp).toDateString() === today
        );
        const falseAlarms = transformedData.filter(q => q.falseAlarm).length;

        setStats({
          total: transformedData.length,
          today: todayQuakes.length,
          falseAlarms: falseAlarms,
          accuracy: transformedData.length > 0
            ? ((transformedData.length - falseAlarms) / transformedData.length * 100).toFixed(1)
            : 0
        });

        // Check for new high-magnitude events for alerts
        const latestEvent = transformedData[0];
        if (latestEvent && latestEvent.magnitude >= 2.0 && !latestEvent.falseAlarm) {
          setActiveAlert(latestEvent);
          setTimeout(() => setActiveAlert(null), 10000);
        }
      } else {
        setIsConnected(false);
        console.error('Failed to fetch earthquake data');
      }
    } catch (error) {
      setIsConnected(false);
      console.error('Error fetching earthquake data:', error);
    }
  };

  // Initial data load and polling
  useEffect(() => {
    // Fetch immediately
    fetchEarthquakeData();

    // Poll every 5 seconds for real-time updates
    const pollInterval = setInterval(fetchEarthquakeData, 5000);

    return () => clearInterval(pollInterval);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Activity className="w-10 h-10 text-orange-500" />
              <h1 className="text-4xl font-bold bg-gradient-to-r from-orange-500 to-red-500 bg-clip-text text-transparent">
                QuakeSense
              </h1>
            </div>
            <p className="text-slate-400 text-lg">Early Earthquake Warning System</p>
          </div>
          {/* Connection Status */}
          <div className="flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-sm text-slate-400">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            {lastUpdate && isConnected && (
              <span className="text-xs text-slate-500">
                Updated {lastUpdate.toLocaleTimeString()} • {earthquakeData.length} events
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Active Alert Banner */}
      {activeAlert && (
        <EarthquakeAlerts alert={activeAlert} onDismiss={() => setActiveAlert(null)} />
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={<Activity className="w-6 h-6" />}
          title="Total Detections"
          value={stats.total}
          color="blue"
        />
        <StatCard
          icon={<TrendingUp className="w-6 h-6" />}
          title="Today's Events"
          value={stats.today}
          color="green"
        />
        <StatCard
          icon={<AlertTriangle className="w-6 h-6" />}
          title="False Alarms"
          value={stats.falseAlarms}
          color="yellow"
        />
        <StatCard
          icon={<Shield className="w-6 h-6" />}
          title="AI Accuracy"
          value={`${stats.accuracy}%`}
          color="purple"
        />
      </div>

      {/* Charts and Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <FrequencyChart data={earthquakeData} />
        <EarthquakeStats data={earthquakeData} />
      </div>

      {/* Earthquake Table */}
      <EarthquakeTable data={earthquakeData} />

      {/* Debug Panel - Remove after testing */}
      {!isConnected && (
        <div className="mt-6 bg-red-500/20 border border-red-500/30 rounded-xl p-6">
          <h3 className="text-red-400 font-bold mb-2">⚠️ Connection Issue Detected</h3>
          <p className="text-sm text-slate-300 mb-2">Cannot connect to backend API</p>
          <p className="text-xs text-slate-400">API URL: {API_BASE_URL}</p>
          <p className="text-xs text-slate-400 mt-2">
            • Make sure backend server is running on port 5000
            <br />
            • Check if IP address {API_BASE_URL.match(/\d+\.\d+\.\d+\.\d+/)?.[0]} is correct
            <br />
            • Open browser console (F12) for detailed error messages
          </p>
        </div>
      )}

      {isConnected && earthquakeData.length === 0 && (
        <div className="mt-6 bg-yellow-500/20 border border-yellow-500/30 rounded-xl p-6">
          <h3 className="text-yellow-400 font-bold mb-2">ℹ️ No Data Available</h3>
          <p className="text-sm text-slate-300">
            Connected to backend, but no earthquake events found.
          </p>
          <p className="text-xs text-slate-400 mt-2">
            • Trigger some earthquakes with your ESP32 device
            <br />
            • Or wait for the ESP32 to send data
            <br />
            • Check backend console to see if events are being received
          </p>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, title, value, color }) {
  const colorClasses = {
    blue: 'from-blue-500/20 to-blue-600/20 border-blue-500/30',
    green: 'from-green-500/20 to-green-600/20 border-green-500/30',
    yellow: 'from-yellow-500/20 to-yellow-600/20 border-yellow-500/30',
    purple: 'from-purple-500/20 to-purple-600/20 border-purple-500/30'
  };

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color]} border rounded-xl p-6 backdrop-blur-sm`}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-slate-300">{icon}</div>
      </div>
      <div className="text-3xl font-bold mb-1">{value}</div>
      <div className="text-sm text-slate-400">{title}</div>
    </div>
  );
}

