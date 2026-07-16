'use client';

import { useEffect, useRef, useState } from 'react';
import { Bell, BellRing, Check, ExternalLink } from 'lucide-react';
import { useRouter } from 'next/navigation';
import {
  acknowledgeOwnerNotification,
  listOwnerNotifications,
  OwnerNotification,
} from '@/lib/api_access';

const POLL_INTERVAL_MS = 15_000;

export default function OwnerNotificationCenter() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<OwnerNotification[]>([]);
  const [open, setOpen] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(() => (
    typeof window !== 'undefined' && 'Notification' in window
      ? Notification.permission
      : 'unsupported'
  ));
  const seenRef = useRef(new Set<string>());
  const fetchingRef = useRef(false);

  useEffect(() => {
    const load = async () => {
      if (fetchingRef.current || document.visibilityState !== 'visible') return;
      fetchingRef.current = true;
      try {
        const items = await listOwnerNotifications();
        setAlerts(items);
        if ('Notification' in window && Notification.permission === 'granted') {
          items.forEach((item) => {
            if (seenRef.current.has(item.id)) return;
            seenRef.current.add(item.id);
            const browserAlert = new Notification(item.title, {
              body: item.message,
              tag: item.id,
              requireInteraction: item.notification_type === 'order_reminder',
            });
            browserAlert.onclick = () => {
              window.focus();
              setOpen(true);
              browserAlert.close();
            };
          });
        }
      } catch {
        // Dashboard data remains usable if notifications are temporarily unavailable.
      } finally {
        fetchingRef.current = false;
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') void load();
    };
    void load();
    const interval = window.setInterval(load, POLL_INTERVAL_MS);
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  const enableDeviceAlerts = async () => {
    if (!('Notification' in window)) return;
    const result = await Notification.requestPermission();
    setPermission(result);
  };

  const openAlert = async (alert: OwnerNotification) => {
    setAlerts((current) => current.filter((item) => item.id !== alert.id));
    await acknowledgeOwnerNotification(alert.id).catch(() => undefined);
    setOpen(false);
    if (alert.action_card_id) {
      router.push(`/action-card?id=${encodeURIComponent(alert.action_card_id)}`);
    } else if (alert.customer_request_id) {
      router.push('/customer-requests');
    }
  };

  const acknowledge = async (alert: OwnerNotification) => {
    setAlerts((current) => current.filter((item) => item.id !== alert.id));
    await acknowledgeOwnerNotification(alert.id).catch(() => {
      setAlerts((current) => current.some((item) => item.id === alert.id) ? current : [...current, alert]);
    });
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="relative inline-flex h-10 w-10 items-center justify-center text-slate-600 hover:bg-slate-100 hover:text-indigo-700 rounded-md"
        title="Order notifications"
        aria-label={`Order notifications${alerts.length ? `, ${alerts.length} unread` : ''}`}
        aria-expanded={open}
      >
        {alerts.some((item) => item.notification_type === 'order_reminder') ? (
          <BellRing className="h-5 w-5" aria-hidden="true" />
        ) : (
          <Bell className="h-5 w-5" aria-hidden="true" />
        )}
        {alerts.length > 0 && (
          <span className="absolute right-0.5 top-0.5 min-w-4 h-4 px-1 bg-red-600 text-white text-[10px] leading-4 font-bold rounded-full">
            {alerts.length > 9 ? '9+' : alerts.length}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-12 z-50 w-[min(22rem,calc(100vw-2rem))] border border-slate-200 bg-white shadow-xl rounded-md overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
            <h2 className="font-bold text-slate-900">Notifications</h2>
            {permission === 'default' && (
              <button type="button" onClick={enableDeviceAlerts} className="text-xs font-semibold text-indigo-700 hover:text-indigo-900">
                Enable device alerts
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {alerts.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-slate-500">No new notifications</p>
            ) : alerts.map((alert) => (
              <div key={alert.id} className="px-4 py-3 border-b border-slate-100 last:border-b-0">
                <p className="text-sm font-bold text-slate-900">{alert.title}</p>
                <p className="mt-1 text-xs leading-5 text-slate-600">{alert.message}</p>
                <div className="mt-2 flex items-center gap-2">
                  <button type="button" onClick={() => openAlert(alert)} className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-700">
                    Open <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                  <button type="button" onClick={() => acknowledge(alert)} className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500">
                    Dismiss <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
