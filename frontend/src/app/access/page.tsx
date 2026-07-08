'use client';

import { useState, useEffect } from 'react';
import QRCode from "react-qr-code";
import { 
  createStaffInvite, 
  listStaffInvites, 
  revokeStaffInvite,
  createStaffAccess, 
  listStaffAccess, 
  revokeStaffAccess
} from '@/lib/api_access';
import { supabase } from '@/lib/supabase/client';

export default function StaffAccessPage() {
  const [invites, setInvites] = useState<any[]>([]);
  const [legacyLinks, setLegacyLinks] = useState<any[]>([]);
  const [shopId, setShopId] = useState<string | null>(null);
  const [role, setRole] = useState('packer');
  const [label, setLabel] = useState('');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [mode, setMode] = useState<'invites' | 'legacy'>('invites');

  useEffect(() => {
    async function load() {
      try {
        if (supabase) {
          const { data: { user } } = await supabase.auth.getUser();
          if (user) {
            const { data: shops } = await supabase.from('shops').select('id').eq('owner_id', user.id);
            if (shops && shops.length > 0) {
              setShopId(shops[0].id);
              const [invitesData, legacyData] = await Promise.all([
                listStaffInvites().catch(() => []),
                listStaffAccess().catch(() => [])
              ]);
              setInvites(invitesData);
              setLegacyLinks(legacyData);
            }
          }
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shopId) return;
    setGenerating(true);
    try {
      if (mode === 'invites') {
        const res = await createStaffInvite(shopId, role, label);
        setInvites([res, ...invites]);
      } else {
        const res = await createStaffAccess(shopId, role, label);
        setLegacyLinks([res, ...legacyLinks]);
      }
      setLabel('');
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async (id: string, isInvite: boolean) => {
    try {
      if (isInvite) {
        await revokeStaffInvite(id);
        setInvites(invites.filter(inv => inv.id !== id));
      } else {
        await revokeStaffAccess(id);
        setLegacyLinks(legacyLinks.filter(link => link.id !== id));
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading...</div>;

  return (
    <div className="space-y-8 p-4 max-w-4xl mx-auto pb-20">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Manage Staff Access</h1>
        <p className="mt-1 text-sm text-slate-500">Generate role-based invites for staff registration.</p>
      </div>
      
      <div className="flex border-b border-slate-200">
        <button 
          onClick={() => setMode('invites')}
          className={`px-4 py-2 font-semibold text-sm transition-colors border-b-2 ${mode === 'invites' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
        >
          Staff Invites (New)
        </button>
        <button 
          onClick={() => setMode('legacy')}
          className={`px-4 py-2 font-semibold text-sm transition-colors border-b-2 ${mode === 'legacy' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
        >
          Legacy Token Links
        </button>
      </div>

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-4">
          Generate New {mode === 'invites' ? 'Invite Code' : 'Legacy Link'}
        </h2>
        <form onSubmit={handleGenerate} className="flex flex-col sm:flex-row gap-4 items-end">
          <div className="flex-1 w-full">
            <label className="block text-sm font-medium text-slate-700 mb-1">Role</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="packer">Packer</option>
              <option value="delivery">Delivery</option>
            </select>
          </div>
          <div className="flex-1 w-full">
            <label className="block text-sm font-medium text-slate-700 mb-1">Label (Optional)</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. John - Morning Shift"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={generating}
            className="w-full sm:w-auto px-6 py-2 bg-indigo-600 text-white rounded-lg font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {generating ? 'Generating...' : 'Generate'}
          </button>
        </form>
      </div>

      {mode === 'invites' && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900 mb-4">Active Staff Invites</h2>
          <div className="space-y-4">
            {invites.map(invite => (
              <div key={invite.id} className="p-4 border border-slate-100 rounded-lg bg-slate-50 flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between">
                <div>
                  <h3 className="font-bold text-slate-800 capitalize">{invite.role} <span className="text-sm font-normal text-slate-500 ml-2">{invite.label || 'No label'}</span></h3>
                  <p className="text-xs text-slate-500 mt-1">Expires: {invite.expires_at ? new Date(invite.expires_at).toLocaleDateString() : 'Never'}</p>
                </div>
                
                <div className="flex-1 w-full max-w-sm">
                  {invite.raw_invite_code ? (
                    <div className="space-y-3">
                      <div>
                        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">Raw Code (Hidden later)</span>
                        <div className="flex">
                          <input readOnly value={invite.raw_invite_code} className="flex-1 px-3 py-1.5 text-sm font-mono bg-white border border-slate-300 rounded-l-md outline-none" />
                          <button onClick={() => navigator.clipboard.writeText(invite.raw_invite_code)} className="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-semibold text-sm rounded-r-md transition-colors border border-l-0 border-slate-300">Copy</button>
                        </div>
                      </div>
                      
                      <div>
                        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">Signup Link</span>
                        <div className="flex">
                          <input readOnly value={`${window.location.origin}/signup?invite=${invite.raw_invite_code}`} className="flex-1 px-3 py-1.5 text-sm font-mono bg-white border border-slate-300 rounded-l-md outline-none" />
                          <button onClick={() => navigator.clipboard.writeText(`${window.location.origin}/signup?invite=${invite.raw_invite_code}`)} className="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-semibold text-sm rounded-r-md transition-colors border border-l-0 border-slate-300">Copy</button>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-4">
                        <div className="w-20 h-20 p-1 bg-white border border-slate-200 rounded">
                          <QRCode 
                            value={`${window.location.origin}/signup?invite=${invite.raw_invite_code}`}
                            size={72}
                            style={{ height: "auto", maxWidth: "100%", width: "100%" }}
                            viewBox={`0 0 256 256`}
                          />
                        </div>
                        <p className="text-xs text-slate-500">Scan QR Code to quickly access the signup page with this invite code pre-filled.</p>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-white border border-slate-200 rounded p-3 text-center">
                      <span className="text-slate-500 text-sm italic font-medium">Invite details are hidden for security.<br/>If lost, revoke and generate a new one.</span>
                    </div>
                  )}
                </div>
                
                <div>
                  <button onClick={() => handleRevoke(invite.id, true)} className="text-red-600 hover:text-red-800 font-semibold text-sm px-4 py-2 border border-red-200 hover:bg-red-50 rounded-lg transition-colors">
                    Revoke
                  </button>
                </div>
              </div>
            ))}
            
            {invites.length === 0 && (
              <div className="py-8 text-center text-slate-500 border-2 border-dashed border-slate-200 rounded-lg">
                No active staff invites found.
              </div>
            )}
          </div>
        </div>
      )}
      
      {mode === 'legacy' && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900 mb-4">Legacy Staff Links</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 text-left">
              <thead>
                <tr className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Label</th>
                  <th className="py-3 px-4">Expires At</th>
                  <th className="py-3 px-4">Access Link</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {legacyLinks.map(link => (
                  <tr key={link.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-semibold text-slate-800 capitalize">{link.role}</td>
                    <td className="py-3 px-4 text-slate-600">{link.label || '-'}</td>
                    <td className="py-3 px-4 text-slate-500">
                      {link.expires_at ? new Date(link.expires_at).toLocaleDateString() : 'Never'}
                    </td>
                    <td className="py-3 px-4">
                      {link.raw_token ? (
                        <div className="flex items-center space-x-2">
                          <input 
                            readOnly 
                            value={`${window.location.origin}/staff/${link.role}?token=${link.raw_token}`}
                            className="px-2 py-1 bg-slate-100 border border-slate-200 rounded text-xs w-48 text-slate-600 outline-none"
                          />
                          <button 
                            onClick={() => navigator.clipboard.writeText(`${window.location.origin}/staff/${link.role}?token=${link.raw_token}`)}
                            className="text-indigo-600 hover:text-indigo-800 text-xs font-semibold"
                          >
                            Copy
                          </button>
                        </div>
                      ) : (
                        <span className="text-slate-400 text-xs italic">Token hash hidden for security</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleRevoke(link.id, false)}
                        className="text-red-600 hover:text-red-800 font-semibold text-xs"
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
                {legacyLinks.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-500">No active legacy links found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
