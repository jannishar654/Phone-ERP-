'use client';

import { FormEvent, useCallback, useEffect, useState } from 'react';
import {
  CheckCircle2,
  ExternalLink,
  Link2,
  Loader2,
  RefreshCw,
  Send,
  Unplug,
  XCircle,
} from 'lucide-react';
import {
  checkTelegramConnection,
  connectTelegram,
  disconnectTelegram,
  getTelegramConnectionStatus,
  TelegramConnectionStatus,
} from '@/lib/api_access';

const INITIAL_STATUS: TelegramConnectionStatus = {
  configured: false,
  status: 'not_connected',
};

function formatDate(value?: string | null) {
  if (!value) return 'Not available';
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export default function TelegramIntegrationPage() {
  const [connection, setConnection] = useState(INITIAL_STATUS);
  const [botToken, setBotToken] = useState('');
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      setError('');
      setConnection(await getTelegramConnectionStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Telegram connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadStatus(), 0);
    return () => window.clearTimeout(timer);
  }, [loadStatus]);

  const connect = async (event: FormEvent) => {
    event.preventDefault();
    setWorking(true);
    setError('');
    setNotice('');
    try {
      const result = await connectTelegram(botToken.trim());
      setConnection(result);
      setBotToken('');
      setNotice('Telegram is connected and ready to receive messages.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Telegram connection failed.');
    } finally {
      setWorking(false);
    }
  };

  const healthCheck = async () => {
    setWorking(true);
    setError('');
    setNotice('');
    try {
      await checkTelegramConnection();
      await loadStatus();
      setNotice('Connection check passed.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Connection check failed.');
      await loadStatus();
    } finally {
      setWorking(false);
    }
  };

  const disconnect = async () => {
    setWorking(true);
    setError('');
    try {
      await disconnectTelegram();
      setConfirmDisconnect(false);
      await loadStatus();
      setNotice('Telegram was disconnected from PhoneERP.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Disconnect failed.');
    } finally {
      setWorking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />Loading integration...
      </div>
    );
  }

  const active = connection.status === 'active';
  const hasError = connection.status === 'error';

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-bold text-slate-900">Telegram Integration</h1>
        <p className="mt-1 text-sm text-slate-600">
          Connect a dedicated Telegram bot owned by this business.
        </p>
      </header>

      {error && <div role="alert" className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {notice && <div role="status" className="border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{notice}</div>}

      <section className="border border-slate-200 bg-white">
        <div className="flex flex-col justify-between gap-4 border-b border-slate-200 p-5 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center bg-sky-50 text-sky-700"><Send className="h-5 w-5" /></div>
            <div>
              <h2 className="font-semibold text-slate-900">Telegram Bot</h2>
              <p className="text-sm text-slate-500">Telegram Bot API</p>
            </div>
          </div>
          <div className={`inline-flex w-fit items-center gap-2 px-3 py-1.5 text-sm font-semibold ${active ? 'bg-emerald-50 text-emerald-700' : hasError ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
            {active ? <CheckCircle2 className="h-4 w-4" /> : hasError ? <XCircle className="h-4 w-4" /> : <Link2 className="h-4 w-4" />}
            {active ? 'Active' : hasError ? 'Connection error' : 'Not connected'}
          </div>
        </div>

        <div className="grid gap-px bg-slate-200 sm:grid-cols-2">
          <div className="bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-400">Bot name</div><div className="mt-1 font-medium text-slate-800">{connection.bot_display_name || 'Not connected'}</div></div>
          <div className="bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-400">Username</div><div className="mt-1 font-medium text-slate-800">{connection.bot_username ? `@${connection.bot_username}` : 'Not connected'}</div></div>
          <div className="bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-400">Last webhook</div><div className="mt-1 text-sm text-slate-700">{formatDate(connection.last_webhook_at)}</div></div>
          <div className="bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-400">Last connection check</div><div className="mt-1 text-sm text-slate-700">{formatDate(connection.last_health_check_at)}</div></div>
        </div>

        {!active && (
          <form className="space-y-4 border-t border-slate-200 p-5" onSubmit={connect}>
            <div>
              <h3 className="font-semibold text-slate-900">Create and connect a bot</h3>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-slate-600">
                <li>Open BotFather and send <code>/newbot</code>.</li>
                <li>Choose the business bot name and username.</li>
                <li>Paste the token below. PhoneERP stores it encrypted.</li>
              </ol>
              <a className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-sky-700 hover:text-sky-800" href="https://t.me/BotFather" rel="noreferrer" target="_blank">Open BotFather <ExternalLink className="h-4 w-4" /></a>
            </div>
            <label className="block text-sm font-medium text-slate-700">
              Bot token
              <input
                autoComplete="off"
                className="mt-1 block w-full border border-slate-300 bg-white px-3 py-2.5 text-slate-900 outline-none focus:border-sky-600"
                onChange={(event) => setBotToken(event.target.value)}
                placeholder="123456789:AA..."
                required
                type="password"
                value={botToken}
              />
            </label>
            <p className="text-xs text-slate-500">Connecting replaces any webhook currently configured for this bot. The token is never shown again.</p>
            <button className="inline-flex items-center gap-2 bg-sky-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-50" disabled={working || !botToken.trim() || !connection.configured} type="submit">
              {working ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}Connect Telegram
            </button>
            {!connection.configured && <p className="text-sm text-amber-700">Secure credential storage must be configured by the PhoneERP administrator.</p>}
          </form>
        )}

        {active && (
          <div className="flex flex-wrap gap-3 border-t border-slate-200 p-5">
            <button className="inline-flex items-center gap-2 border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50" disabled={working} onClick={healthCheck}><RefreshCw className={`h-4 w-4 ${working ? 'animate-spin' : ''}`} />Test connection</button>
            {!confirmDisconnect && <button className="inline-flex items-center gap-2 border border-red-200 bg-white px-4 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50" disabled={working} onClick={() => setConfirmDisconnect(true)}><Unplug className="h-4 w-4" />Disconnect</button>}
          </div>
        )}

        {confirmDisconnect && (
          <div className="border-t border-red-200 bg-red-50 p-5">
            <p className="text-sm text-red-800">New Telegram messages will stop routing to this business immediately.</p>
            <div className="mt-3 flex gap-3">
              <button className="bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={working} onClick={disconnect}>Confirm disconnect</button>
              <button className="border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700" disabled={working} onClick={() => setConfirmDisconnect(false)}>Keep connected</button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
