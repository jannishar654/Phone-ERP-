import React from 'react';

interface MetricCardProps {
  name: string;
  value: string | number;
  color: string;
  isLoading?: boolean;
}

export default function MetricCard({ name, value, isLoading }: MetricCardProps) {
  // Determine styles and icon based on metric name
  let icon: React.ReactNode;
  let bgClass = 'bg-slate-50';
  let valueColorClass = 'text-slate-900';

  if (name === 'Total Orders') {
    bgClass = 'bg-indigo-50 text-indigo-600';
    valueColorClass = 'text-slate-900';
    icon = (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9h6m-6-4h6" />
      </svg>
    );
  } else if (name === 'Pending Orders') {
    bgClass = 'bg-orange-50 text-orange-500';
    valueColorClass = 'text-orange-500';
    icon = (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    );
  } else if (name === 'Approved Orders') {
    bgClass = 'bg-emerald-50 text-emerald-600';
    valueColorClass = 'text-emerald-600';
    icon = (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    );
  } else if (name === 'Delivered Orders') {
    bgClass = 'bg-blue-50 text-blue-600';
    valueColorClass = 'text-blue-600';
    icon = (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 17a2 2 0 11-4 0 2 2 0 014 0zM18 17a2 2 0 11-4 0 2 2 0 014 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M18 15h1a1 1 0 001-1v-4a1 1 0 00-.3-.7l-2.7-2.7A1 1 0 0016.3 6H13v9m0 0V4a1 1 0 00-1-1H4a1 1 0 00-1 1v11h15z" />
      </svg>
    );
  } else {
    icon = (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 flex items-center space-x-5 shadow-xs">
      <div className={`p-4 rounded-2xl flex items-center justify-center shrink-0 ${bgClass}`}>
        {icon}
      </div>
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-semibold text-slate-500 truncate">{name}</span>
        {isLoading ? (
          <span className="text-3xl font-extrabold text-slate-300 animate-pulse mt-0.5">--</span>
        ) : (
          <span className={`text-3xl font-extrabold tracking-tight mt-0.5 ${valueColorClass}`}>
            {value}
          </span>
        )}
      </div>
    </div>
  );
}
