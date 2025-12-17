import { AlertTriangle, X } from 'lucide-react';

export default function EarthquakeAlerts({ alert, onDismiss }) {
  if (!alert) return null;

  const getSeverityColor = (magnitude) => {
    if (magnitude >= 6) return 'from-red-600 to-red-700 border-red-500';
    if (magnitude >= 5) return 'from-orange-600 to-orange-700 border-orange-500';
    if (magnitude >= 4) return 'from-yellow-600 to-yellow-700 border-yellow-500';
    return 'from-blue-600 to-blue-700 border-blue-500';
  };

  const getSeverityText = (magnitude) => {
    if (magnitude >= 6) return 'SEVERE';
    if (magnitude >= 5) return 'HIGH';
    if (magnitude >= 4) return 'MODERATE';
    return 'LOW';
  };

  return (
    <div className={`bg-gradient-to-r ${getSeverityColor(alert.magnitude)} border-2 rounded-xl p-6 mb-8 animate-pulse shadow-2xl`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <AlertTriangle className="w-8 h-8 text-white flex-shrink-0 mt-1" />
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-2xl font-bold text-white">
                EARTHQUAKE DETECTED
              </h2>
              <span className="px-3 py-1 bg-white/20 rounded-full text-sm font-bold">
                {getSeverityText(alert.magnitude)}
              </span>
            </div>
            <div className="space-y-1 text-white/90">
              <p className="text-lg">
                <span className="font-semibold">Magnitude:</span> {alert.magnitude} m/s²
              </p>
              <p className="text-lg">
                <span className="font-semibold">Device:</span> {alert.location}
              </p>
              <p>
                <span className="font-semibold">AI Confidence:</span> {alert.confidence}%
              </p>
              {alert.falseAlarm && (
                <p className="text-yellow-200 font-semibold">
                  ⚠ AI flagged as potential false alarm
                </p>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="text-white/70 hover:text-white transition-colors"
        >
          <X className="w-6 h-6" />
        </button>
      </div>
    </div>
  );
}
