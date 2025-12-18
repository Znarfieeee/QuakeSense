import { TrendingUp } from 'lucide-react';
import { useState, useMemo } from 'react';

export default function FrequencyChart({ data }) {
  const [timeRange, setTimeRange] = useState('today'); // today, 7d, 30d

  const chartData = useMemo(() => {
    let days, labels, frequencies;

    if (timeRange === 'today') {
      // Show hourly data for today
      const now = new Date();
      const hours = 24;
      frequencies = new Array(hours).fill(0);
      labels = [];

      for (let i = 0; i < hours; i++) {
        const hour = i;
        labels.push(`${hour}:00`);

        // Count earthquakes for this hour
        const hourStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, 0, 0);
        const hourEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, 59, 59);

        frequencies[i] = data.filter(quake => {
          const quakeDate = new Date(quake.timestamp);
          return quakeDate >= hourStart && quakeDate <= hourEnd;
        }).length;
      }
    } else {
      // Show daily data for 7d or 30d
      days = timeRange === '7d' ? 7 : 30;
      const now = new Date();
      frequencies = new Array(days).fill(0);
      labels = [];

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
    }

    return { frequencies, labels };
  }, [data, timeRange]);

  const maxFrequency = Math.max(...chartData.frequencies, 1);

  // Generate smooth SVG path for line chart using quadratic curves
  const generateLinePath = () => {
    const width = 100; // percentage
    const height = 100; // percentage
    const points = chartData.frequencies.length;
    const xStep = width / (points - 1 || 1);

    const pathPoints = chartData.frequencies.map((freq, index) => ({
      x: index * xStep,
      y: height - (freq / maxFrequency) * height
    }));

    if (pathPoints.length < 2) return '';

    // Create smooth curve using quadratic bezier curves
    let path = `M ${pathPoints[0].x} ${pathPoints[0].y}`;

    for (let i = 0; i < pathPoints.length - 1; i++) {
      const current = pathPoints[i];
      const next = pathPoints[i + 1];

      // Control point for smooth curve (midpoint with slight offset)
      const controlX = (current.x + next.x) / 2;
      const controlY = (current.y + next.y) / 2;

      path += ` Q ${controlX} ${controlY}, ${next.x} ${next.y}`;
    }

    return path;
  };

  // Generate smooth area path (filled area under line)
  const generateAreaPath = () => {
    const width = 100;
    const height = 100;
    const points = chartData.frequencies.length;
    const xStep = width / (points - 1 || 1);

    const pathPoints = chartData.frequencies.map((freq, index) => ({
      x: index * xStep,
      y: height - (freq / maxFrequency) * height
    }));

    if (pathPoints.length < 2) return '';

    // Start from bottom left
    let path = `M 0,${height} L ${pathPoints[0].x},${pathPoints[0].y}`;

    // Create smooth curve matching the line
    for (let i = 0; i < pathPoints.length - 1; i++) {
      const current = pathPoints[i];
      const next = pathPoints[i + 1];
      const controlX = (current.x + next.x) / 2;
      const controlY = (current.y + next.y) / 2;
      path += ` Q ${controlX} ${controlY}, ${next.x} ${next.y}`;
    }

    // Close path at bottom right
    path += ` L ${width},${height} Z`;
    return path;
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 backdrop-blur-sm transition-all duration-300 hover:border-slate-600 hover:shadow-xl hover:shadow-orange-500/5">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-orange-500" />
          <h2 className="text-xl font-bold">Earthquake Frequency</h2>
        </div>
        <div className="flex gap-2">
          {[
            { value: 'today', label: 'Today' },
            { value: '7d', label: '7 Days' },
            { value: '30d', label: '30 Days' }
          ].map((range) => (
            <button
              key={range.value}
              onClick={() => setTimeRange(range.value)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all duration-300 ${
                timeRange === range.value
                  ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow-lg shadow-orange-500/30 scale-105'
                  : 'bg-slate-700/50 text-slate-300 hover:bg-slate-600/70 hover:scale-105 hover:shadow-md'
              }`}
            >
              {range.label}
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

        {/* Line Chart */}
        <div className="ml-8 h-full relative">
          <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <defs>
              {/* Enhanced gradient with multiple stops */}
              <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="rgb(251 146 60)" stopOpacity="0.6" />
                <stop offset="50%" stopColor="rgb(249 115 22)" stopOpacity="0.3" />
                <stop offset="100%" stopColor="rgb(234 88 12)" stopOpacity="0.05" />
              </linearGradient>

              {/* Glow effect for line */}
              <filter id="glow">
                <feGaussianBlur stdDeviation="1" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>

              {/* Shadow for data points */}
              <filter id="shadow">
                <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodOpacity="0.5" floodColor="rgb(251 146 60)"/>
              </filter>
            </defs>

            {/* Grid lines with subtle styling */}
            <line x1="0" y1="0" x2="100" y2="0" stroke="rgb(71 85 105)" strokeWidth="0.3" opacity="0.5" />
            <line x1="0" y1="25" x2="100" y2="25" stroke="rgb(51 65 85)" strokeWidth="0.2" strokeDasharray="1,2" opacity="0.3" />
            <line x1="0" y1="50" x2="100" y2="50" stroke="rgb(51 65 85)" strokeWidth="0.3" strokeDasharray="2,2" opacity="0.5" />
            <line x1="0" y1="75" x2="100" y2="75" stroke="rgb(51 65 85)" strokeWidth="0.2" strokeDasharray="1,2" opacity="0.3" />
            <line x1="0" y1="100" x2="100" y2="100" stroke="rgb(71 85 105)" strokeWidth="0.3" opacity="0.5" />

            {/* Area fill with enhanced gradient */}
            <path
              d={generateAreaPath()}
              fill="url(#areaGradient)"
              className="transition-all duration-700 ease-in-out"
            />

            {/* Line */}
            <path
              d={generateLinePath()}
              fill="none"
              stroke="rgb(251 146 60)"
              strokeWidth="1"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="transition-all duration-700 ease-in-out"
            />

            {/* Data points with enhanced interactivity */}
            {chartData.frequencies.map((freq, index) => {
              const width = 100;
              const height = 100;
              const xStep = width / (chartData.frequencies.length - 1 || 1);
              const x = index * xStep;
              const y = height - (freq / maxFrequency) * height;

              return (
                <g key={index}>
                  {/* Larger invisible hover area */}
                  <circle
                    cx={x}
                    cy={y}
                    r="5"
                    fill="transparent"
                    className="cursor-pointer"
                  >
                    <title>{freq} event{freq !== 1 ? 's' : ''}</title>
                  </circle>

                  {/* Visible data point */}
                  <circle
                    cx={x}
                    cy={y}
                    r="2"
                    fill="rgb(251 146 60)"
                    filter="url(#shadow)"
                    className="transition-all duration-200 hover:scale-150"
                    style={{ transformOrigin: `${x}% ${y}%` }}
                  />

                  {/* Outer ring on hover */}
                  <circle
                    cx={x}
                    cy={y}
                    r="3.5"
                    fill="none"
                    stroke="rgb(251 146 60)"
                    strokeWidth="0.5"
                    opacity="0"
                    className="transition-all duration-200 hover:opacity-60"
                  />
                </g>
              );
            })}
          </svg>
        </div>

        {/* X-axis labels */}
        <div className="ml-8 mt-2 flex justify-between text-xs text-slate-400">
          {chartData.labels.map((label, index) => {
            // Show fewer labels for better readability
            const showLabel =
              timeRange === 'today' ? index % 3 === 0 :
              timeRange === '7d' ? true :
              index % 3 === 0;

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
          <div className="text-xs text-slate-400">Avg per {timeRange === 'today' ? 'Hour' : 'Day'}</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-purple-400">
            {Math.max(...chartData.frequencies)}
          </div>
          <div className="text-xs text-slate-400">Peak {timeRange === 'today' ? 'Hour' : 'Day'}</div>
        </div>
      </div>
    </div>
  );
}
