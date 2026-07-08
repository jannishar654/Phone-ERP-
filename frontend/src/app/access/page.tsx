'use client';

import { useState, useEffect } from 'react';
import { createStaffAccess, listStaffAccess, revokeStaffAccess } from '@/lib/api_access';
import { getOrders } from '@/lib/api';
import { supabase } from '@/lib/supabase/client';

export default function StaffAccessPage() {
  const [links, setLinks] = useState<any[]>([]);
  const [shopId, setShopId] = useState<string | null>(null);
  const [role, setRole] = useState('packer');
  const [label, setLabel] = useState('');
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        if (supabase) {
          const { data: { user } } = await supabase.auth.getUser();
          if (user) {
            const { data: shops } = await supabase.from('shops').select('id').eq('owner_id', user.id);
            if (shops && shops.length > 0) {
              setShopId(shops[0].id);
              const accessLinks = await listStaffAccess();
              setLinks(accessLinks);
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
      const res = await createStaffAccess(shopId, role, label);
      setLinks([res, ...links]);
      setLabel('');
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  const handleRevoke = async (id: string) => {
    try {
      await revokeStaffAccess(id);
      setLinks(links.filter(link => link.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Loading...</div>;

  return (
    <div className="space-y-8 p-4 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-900">Manage Staff Access</h1>
        <p className="mt-1 text-sm text-slate-500">Generate and revoke token links for packing and delivery staff.</p>
      </div>

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-4">Generate New Link</h2>
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
            {generating ? 'Generating...' : 'Generate Link'}
          </button>
        </form>
      </div>

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900 mb-4">Active Staff Links</h2>
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
              {links.map(link => (
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
                      onClick={() => handleRevoke(link.id)}
                      className="text-red-600 hover:text-red-800 font-semibold text-xs"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
              {links.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500">No active staff links found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
