const scoreColor = (value = 0) => {
  if (value >= 80) return "bg-emerald-600";
  if (value >= 50) return "bg-amber-500";
  return "bg-red-500";
};

export const ScoreBar = ({ value = 0, label, compact = false }) => {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="w-full">
      <div className="mb-2 flex items-center justify-between gap-3">
        {label && <span className="text-sm font-medium text-slate-600">{label}</span>}
        <span className={`${compact ? "text-sm" : "text-lg"} font-semibold text-slate-950`}>
          {safeValue}%
        </span>
      </div>
      <div className="h-2.5 rounded-full bg-slate-100">
        <div className={`h-2.5 rounded-full ${scoreColor(safeValue)}`} style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  );
};

const ScoreGauge = ({ value = 0, label = "Score" }) => {
  const safeValue = Math.max(0, Math.min(100, Number(value) || 0));
  const color = safeValue >= 80 ? "#059669" : safeValue >= 50 ? "#d97706" : "#dc2626";
  return (
    <div className="flex items-center gap-4">
      <div
        className="grid h-24 w-24 shrink-0 place-items-center rounded-full"
        style={{ background: `conic-gradient(${color} ${safeValue * 3.6}deg, #e5e7eb 0deg)` }}
      >
        <div className="grid h-18 w-18 place-items-center rounded-full bg-white">
          <span className="text-2xl font-semibold text-slate-950">{safeValue}</span>
        </div>
      </div>
      <div>
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <p className="mt-1 text-sm text-slate-500">Red under 50, amber 50-79, green 80+</p>
      </div>
    </div>
  );
};

export default ScoreGauge;
