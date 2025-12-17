import { AlertCircle, CheckCircle, Clock, MapPin, Gauge } from 'lucide-react';
import { useState } from 'react';

export default function EarthquakeTable({ data }) {
  const [filter, setFilter] = useState('all'); // all, real, false

  const filteredData = data.filter(quake => {
    if (filter === 'real') return !quake.falseAlarm;
    if (filter === 'false') return quake.falseAlarm;
    return true;
  });

  const getMagnitudeColor = (magnitude) => {
    const mag = parseFloat(magnitude);
    if (mag >= 6) return 'text-red-500 bg-red-500/10';
    if (mag >= 5) return 'text-orange-500 bg-orange-500/10';
    if (mag >= 4) return 'text-yellow-500 bg-yellow-500/10';
    return 'text-blue-500 bg-blue-500/10';
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden backdrop-blur-sm">
      {/* Header */}
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">Recent Detections</h2>
          <div className="flex gap-2">
            {[
              { value: 'all', label: 'All' },
              { value: 'real', label: 'Real' },
              { value: 'false', label: 'False Alarms' }
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => setFilter(option.value)}
                className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                  filter === option.value
                    ? 'bg-orange-500 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-900/50">
            <tr className="text-left text-sm text-slate-400">
              <th className="p-4 font-medium">Time</th>
              <th className="p-4 font-medium">Magnitude</th>
              <th className="p-4 font-medium">Device</th>
              <th className="p-4 font-medium">AI Confidence</th>
              <th className="p-4 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {filteredData.length === 0 ? (
              <tr>
                <td colSpan="5" className="p-8 text-center text-slate-400">
                  No earthquake data found
                </td>
              </tr>
            ) : (
              filteredData.slice(0, 15).map((quake) => (
                <tr
                  key={quake.id}
                  className="hover:bg-slate-700/30 transition-colors"
                >
                  <td className="p-4">
                    <div className="flex items-center gap-2 text-sm">
                      <Clock className="w-4 h-4 text-slate-500" />
                      <span>{formatTimestamp(quake.timestamp)}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <Gauge className="w-4 h-4 text-slate-500" />
                      <span className={`px-3 py-1 rounded-full text-sm font-bold ${getMagnitudeColor(quake.magnitude)}`}>
                        {quake.magnitude} m/s²
                      </span>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2 text-sm">
                      <MapPin className="w-4 h-4 text-slate-500" />
                      <span className="max-w-xs truncate">{quake.location}</span>
                    </div>
                  </td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            quake.confidence >= 80
                              ? 'bg-green-500'
                              : quake.confidence >= 60
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                          }`}
                          style={{ width: `${quake.confidence}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium w-12 text-right">
                        {quake.confidence}%
                      </span>
                    </div>
                  </td>
                  <td className="p-4">
                    {quake.falseAlarm ? (
                      <div className="flex items-center gap-2 text-yellow-500">
                        <AlertCircle className="w-5 h-5" />
                        <span className="text-sm font-medium">False Alarm</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-green-500">
                        <CheckCircle className="w-5 h-5" />
                        <span className="text-sm font-medium">Confirmed</span>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
