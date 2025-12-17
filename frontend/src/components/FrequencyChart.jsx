import { BarChart3 } from 'lucide-react';
import { useState, useMemo } from 'react';

export default function FrequencyChart({ data }) {
  const [timeRange, setTimeRange] = useState('7d'); // 7d, 30d, 90d

  const chartData = useMemo(() => {
    const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90;
    const now = new Date();
    const frequencies = new Array(days).fill(0);
    const labels = [];

    // Generate labels and count earthquakes per day
    for (let i = days - 1; i >= 0; i--) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);
      labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));

      // Count earthquakes for this day
      const dayStart = new Date(date.setHours(0, 0, 0, 0));
      const dayEnd = new Date(date.setHours(23, 59, 59, 999));

      frequencies[days - 1 - i] = data.filter(quake => {
        const quakeDate = new Date(quake.timestamp);
        return quakeDate >= dayStart && quakeDate <= dayEnd;
      }).length;
    }

    return { frequencies, labels };
  }, [data, timeRange]);

  const maxFrequency = Math.max(...chartData.frequencies, 1);

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-orange-500" />
          <h2 className="text-xl font-bold">Earthquake Frequency</h2>
        </div>
        <div className="flex gap-2">
          {['7d', '30d', '90d'].map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                timeRange === range
                  ? 'bg-orange-500 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      <div className="relative h-64">
        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-between text-xs text-slate-400 pr-2">
          <span>{maxFrequency}</span>
          <span>{Math.floor(maxFrequency / 2)}</span>
          <span>0</span>
        </div>

        {/* Chart area */}
        <div className="ml-8 h-full flex items-end justify-between gap-1">
          {chartData.frequencies.map((freq, index) => (
            <div key={index} className="flex-1 flex flex-col items-center group">
              <div
                className="w-full bg-gradient-to-t from-orange-600 to-orange-400 rounded-t-sm transition-all duration-300 hover:from-orange-500 hover:to-orange-300 relative"
                style={{ height: `${(freq / maxFrequency) * 100}%`, minHeight: freq > 0 ? '4px' : '0' }}
              >
                {freq > 0 && (
                  <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-slate-900 px-2 py-1 rounded text-xs font-semibold opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                    {freq} event{freq !== 1 ? 's' : ''}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* X-axis labels */}
        <div className="ml-8 mt-2 flex justify-between text-xs text-slate-400">
          {chartData.labels.map((label, index) => {
            // Show fewer labels for better readability
            const showLabel = timeRange === '7d' || index % 3 === 0;
            return (
              <span key={index} className={`flex-1 text-center ${showLabel ? '' : 'invisible'}`}>
                {label}
              </span>
            );
          })}
        </div>
      </div>

      {/* Summary stats */}
      <div className="mt-6 pt-6 border-t border-slate-700 grid grid-cols-3 gap-4">
        <div className="text-center">
          <div className="text-2xl font-bold text-orange-400">
            {chartData.frequencies.reduce((a, b) => a + b, 0)}
          </div>
          <div className="text-xs text-slate-400">Total Events</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-400">
            {(chartData.frequencies.reduce((a, b) => a + b, 0) / chartData.frequencies.length).toFixed(1)}
          </div>
          <div className="text-xs text-slate-400">Avg per Day</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-purple-400">
            {Math.max(...chartData.frequencies)}
          </div>
          <div className="text-xs text-slate-400">Peak Day</div>
        </div>
      </div>
    </div>
  );
}
