import { useEffect, useState, useRef } from 'react';

export function useAutoRefresh(callback: (isSilent: boolean) => Promise<void>, intervalMs: number = 10000) {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const isFetchingRef = useRef(false);
  const callbackRef = useRef(callback);

  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  const fetchWithGuard = async (isSilent: boolean = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    try {
      await callbackRef.current(isSilent);
      setLastUpdated(new Date());
      setRefreshError(null);
    } catch (err: any) {
      setRefreshError(err.message || 'Background refresh failed');
    } finally {
      isFetchingRef.current = false;
    }
  };

  useEffect(() => {
    fetchWithGuard(false); // Initial load

    let interval: ReturnType<typeof setInterval> | null = null;

    const startInterval = () => {
      if (interval) clearInterval(interval);
      interval = setInterval(() => {
        if (document.visibilityState === 'visible') {
          fetchWithGuard(true);
        }
      }, intervalMs);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchWithGuard(true);
        startInterval();
      } else {
        if (interval) {
          clearInterval(interval);
          interval = null;
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    startInterval();

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (interval) clearInterval(interval);
    };
  }, [intervalMs]);

  const manualRefresh = () => fetchWithGuard(false);
  const silentRefresh = () => fetchWithGuard(true);

  return { lastUpdated, refreshError, manualRefresh, silentRefresh };
}
