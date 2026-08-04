'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, Link2, Loader2, MessageCircle, RefreshCw, Unplug, XCircle } from 'lucide-react';
import {
  checkWhatsAppConnection,
  completeWhatsAppOnboarding,
  createWhatsAppOnboardingSession,
  disconnectWhatsApp,
  getWhatsAppConnectionStatus,
  WhatsAppConnectionStatus,
  WhatsAppOnboardingSession,
} from '@/lib/api_access';

type EmbeddedSignupAsset = { waba_id?: string; phone_number_id?: string };
type FacebookLoginResponse = { authResponse?: { code?: string }; status?: string };
type FacebookSDK = {
  init: (options: Record<string, unknown>) => void;
  login: (
    callback: (response: FacebookLoginResponse) => void,
    options: Record<string, unknown>,
  ) => void;
};

declare global {
  interface Window {
    FB?: FacebookSDK;
    fbAsyncInit?: () => void;
  }
}

const INITIAL_STATUS: WhatsAppConnectionStatus = {
  embedded_signup_enabled: false,
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

async function loadFacebookSDK(session: WhatsAppOnboardingSession): Promise<FacebookSDK> {
  if (window.FB) return window.FB;
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => reject(new Error('Meta signup could not be loaded.')), 12_000);
    window.fbAsyncInit = () => {
      window.FB?.init({
        appId: session.app_id,
        autoLogAppEvents: true,
        xfbml: false,
        version: session.graph_api_version,
      });
      window.clearTimeout(timeout);
      if (window.FB) resolve(window.FB);
      else reject(new Error('Meta signup could not be initialized.'));
    };
    const existing = document.getElementById('facebook-jssdk');
    if (existing) existing.remove();
    const script = document.createElement('script');
    script.id = 'facebook-jssdk';
    script.async = true;
    script.defer = true;
    script.crossOrigin = 'anonymous';
    script.src = 'https://connect.facebook.net/en_US/sdk.js';
    script.onerror = () => {
      window.clearTimeout(timeout);
      reject(new Error('Meta signup could not be loaded.'));
    };
    document.body.appendChild(script);
  });
}

export default function WhatsAppIntegrationPage() {
  const [connection, setConnection] = useState(INITIAL_STATUS);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [registrationPin, setRegistrationPin] = useState('');
  const assetRef = useRef<EmbeddedSignupAsset>({});
  const assetResolverRef = useRef<((asset: EmbeddedSignupAsset) => void) | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setError('');
      setConnection(await getWhatsAppConnectionStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load WhatsApp connection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadStatus(), 0);
    return () => window.clearTimeout(timer);
  }, [loadStatus]);

  useEffect(() => {
    const receiveMetaSession = (event: MessageEvent) => {
      if (event.origin !== 'https://www.facebook.com' && event.origin !== 'https://web.facebook.com') return;
      let payload = event.data;
      if (typeof payload === 'string') {
        try { payload = JSON.parse(payload); } catch { return; }
      }
      if (payload?.type !== 'WA_EMBEDDED_SIGNUP' || payload?.event !== 'FINISH') return;
      assetRef.current = {
        waba_id: payload.data?.waba_id,
        phone_number_id: payload.data?.phone_number_id,
      };
      assetResolverRef.current?.(assetRef.current);
      assetResolverRef.current = null;
    };
    window.addEventListener('message', receiveMetaSession);
    return () => window.removeEventListener('message', receiveMetaSession);
  }, []);

  const connect = async () => {
    setWorking(true);
    setError('');
    setNotice('');
    assetRef.current = {};
    const assetPromise = new Promise<EmbeddedSignupAsset>((resolve) => {
      assetResolverRef.current = resolve;
    });
    try {
      const session = await createWhatsAppOnboardingSession();
      const facebook = await loadFacebookSDK(session);
      facebook.login(async (response) => {
        const code = response.authResponse?.code;
        if (!code) {
          assetResolverRef.current = null;
          setWorking(false);
          if (response.status !== 'connected') setError('Meta signup was cancelled or not completed.');
          return;
        }
        try {
          const selectedAsset = assetRef.current.phone_number_id
            ? assetRef.current
            : await Promise.race([
                assetPromise,
                new Promise<EmbeddedSignupAsset>((resolve) => {
                  window.setTimeout(() => resolve(assetRef.current), 2_000);
                }),
              ]);
          const result = await completeWhatsAppOnboarding({
            state: session.state,
            code,
            ...selectedAsset,
            registration_pin: registrationPin,
          });
          setConnection(result);
          setNotice('WhatsApp is connected and ready to receive business messages.');
        } catch (err) {
          setError(err instanceof Error ? err.message : 'WhatsApp connection failed.');
        } finally {
          assetResolverRef.current = null;
          setWorking(false);
        }
      }, {
        config_id: session.configuration_id,
        response_type: 'code',
        override_default_response_type: true,
        extras: { sessionInfoVersion: '3' },
      });
    } catch (err) {
      assetResolverRef.current = null;
      setError(err instanceof Error ? err.message : 'WhatsApp connection failed.');
      setWorking(false);
    }
  };

  const healthCheck = async () => {
    setWorking(true);
    setError('');
    setNotice('');
    try {
      await checkWhatsAppConnection();
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
      await disconnectWhatsApp();
      setConfirmDisconnect(false);
      await loadStatus();
      setNotice('WhatsApp was disconnected from PhoneERP.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Disconnect failed.');
    } finally {
      setWorking(false);
    }
  };

  if (loading) {
    return <div className="flex min-h-[50vh] items-center justify-center text-slate-500"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Loading integration...</div>;
  }

  const active = connection.status === 'active';
  const needsReconnect = connection.status === 'reconnect_required' || connection.status === 'error';

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-bold text-slate-900">WhatsApp Integration</h1>
        <p className="mt-1 text-sm text-slate-600">Connect the WhatsApp number owned by this business.</p>
      </header>

      {error && <div role="alert" className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {notice && <div role="status" className="border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{notice}</div>}

      <section className="border border-slate-200 bg-white">
        <div className="flex flex-col justify-between gap-4 border-b border-slate-200 p-5 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center bg-emerald-50 text-emerald-700"><MessageCircle className="h-5 w-5" /></div>
            <div>
              <h2 className="font-semibold text-slate-900">WhatsApp Business Platform</h2>
              <p className="text-sm text-slate-500">Meta Cloud API</p>
            </div>
          </div>
          <div className={`inline-flex w-fit items-center gap-2 px-3 py-1.5 text-sm font-semibold ${active ? 'bg-emerald-50 text-emerald-700' : needsReconnect ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>
            {active ? <CheckCircle2 className="h-4 w-4" /> : needsReconnect ? <XCircle className="h-4 w-4" /> : <Link2 className="h-4 w-4" />}
            {active ? 'Active' : needsReconnect ? 'Reconnect required' : 'Not connected'}
          </div>
        </div>

        <div className="grid gap-px bg-slate-200 sm:grid-cols-2">
          <div className="bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-400">Business name</div><div className="mt-1 font-medium text-slate-800">{connection.verified_name || 'Not connected'}</div></div>
          <div className="bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-400">WhatsApp number</div><div className="mt-1 font-medium text-slate-800">{connection.display_phone_number || 'Not connected'}</div></div>
          <div className="bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-400">Last webhook</div><div className="mt-1 text-sm text-slate-700">{formatDate(connection.last_webhook_at)}</div></div>
          <div className="bg-white p-5"><div className="text-xs font-semibold uppercase text-slate-400">Last connection check</div><div className="mt-1 text-sm text-slate-700">{formatDate(connection.last_health_check_at)}</div></div>
        </div>

        <div className="flex flex-wrap gap-3 border-t border-slate-200 p-5">
          {!active && (
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:items-end">
              <label className="text-sm font-medium text-slate-700">
                Cloud API PIN
                <input
                  aria-describedby="cloud-api-pin-note"
                  autoComplete="new-password"
                  className="mt-1 block w-40 border border-slate-300 bg-white px-3 py-2 text-slate-900 outline-none focus:border-emerald-600"
                  inputMode="numeric"
                  maxLength={6}
                  onChange={(event) => setRegistrationPin(event.target.value.replace(/\D/g, '').slice(0, 6))}
                  pattern="[0-9]{6}"
                  placeholder="6 digits"
                  type="password"
                  value={registrationPin}
                />
              </label>
              <button disabled={working || registrationPin.length !== 6 || !connection.embedded_signup_enabled || !connection.configured} onClick={connect} className="inline-flex h-10 items-center justify-center gap-2 bg-emerald-600 px-4 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">
                {working ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}{needsReconnect ? 'Reconnect WhatsApp' : 'Connect WhatsApp'}
              </button>
            </div>
          )}
          {active && <button disabled={working} onClick={healthCheck} className="inline-flex items-center gap-2 border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${working ? 'animate-spin' : ''}`} />Test connection</button>}
          {active && connection.embedded_signup_enabled && !confirmDisconnect && <button disabled={working} onClick={() => setConfirmDisconnect(true)} className="inline-flex items-center gap-2 border border-red-200 bg-white px-4 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"><Unplug className="h-4 w-4" />Disconnect</button>}
        </div>

        {confirmDisconnect && (
          <div className="border-t border-red-200 bg-red-50 p-5">
            <p className="text-sm text-red-800">New messages will stop routing to this PhoneERP business immediately.</p>
            <div className="mt-3 flex gap-3">
              <button disabled={working} onClick={disconnect} className="bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Confirm disconnect</button>
              <button disabled={working} onClick={() => setConfirmDisconnect(false)} className="border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700">Keep connected</button>
            </div>
          </div>
        )}
      </section>

      {!connection.embedded_signup_enabled && (
        <div className="border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">Business onboarding is currently limited to supervised pilots while Meta approval is completed.</div>
      )}
      {!active && connection.embedded_signup_enabled && (
        <p id="cloud-api-pin-note" className="text-xs text-slate-500">Use the business&apos;s existing two-step PIN, or choose a new six-digit PIN for a new Cloud API number.</p>
      )}
    </div>
  );
}
