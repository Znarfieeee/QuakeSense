import { PieChart } from 'lucide-react';

export default function EarthquakeStats({ data }) {
  // Calculate magnitude distribution
  const getMagnitudeDistribution = () => {
    const ranges = {
      'Minor (< 3.0)': 0,
      'Light (3.0-3.9)': 0,
      'Moderate (4.0-4.9)': 0,
      'Strong (5.0-5.9)': 0,
      'Major (≥ 6.0)': 0
    };

    data.forEach(quake => {
      const mag = parseFloat(quake.magnitude);
      if (mag < 3) ranges['Minor (< 3.0)']++;
      else if (mag < 4) ranges['Light (3.0-3.9)']++;
      else if (mag < 5) ranges['Moderate (4.0-4.9)']++;
      else if (mag < 6) ranges['Strong (5.0-5.9)']++;
      else ranges['Major (≥ 6.0)']++;
    });

    return ranges;
  };

  const distribution = getMagnitudeDistribution();
  const maxValue = Math.max(...Object.values(distribution));

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 backdrop-blur-sm">
      <div className="flex items-center gap-2 mb-6">
        <PieChart className="w-5 h-5 text-orange-500" />
        <h2 className="text-xl font-bold">Magnitude Distribution</h2>
      </div>

      <div className="space-y-4">
        {Object.entries(distribution).map(([range, count]) => (
          <div key={range}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-slate-300">{range}</span>
              <span className="font-semibold">{count}</span>
            </div>
            <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-orange-500 to-red-500 rounded-full transition-all duration-500"
                style={{ width: `${maxValue ? (count / maxValue) * 20 : 0}%` }}
              />
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}
