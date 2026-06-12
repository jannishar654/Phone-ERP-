interface MetricCardProps {
  name: string;
  value: string | number;
  color: string;
  isLoading?: boolean;
}

export default function MetricCard({ name, value, color, isLoading }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 flex flex-col justify-between shadow-sm">
      <span className="text-sm font-semibold text-slate-500">{name}</span>
      <div className="mt-4 flex items-baseline justify-between">
        {isLoading ? (
          <span className="text-3xl font-bold text-slate-300 animate-pulse">--</span>
        ) : (
          <span className={`text-3xl font-extrabold tracking-tight ${color}`}>
            {value}
          </span>
        )}
      </div>
    </div>
  );
}
