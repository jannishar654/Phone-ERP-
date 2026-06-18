import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || ''
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''

export const supabase = (supabaseUrl && supabaseAnonKey && supabaseUrl !== 'your-vercel-supabase-url') 
  ? createClient(supabaseUrl, supabaseAnonKey) 
  : null;

// Simple cookie helpers
function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const nameEQ = name + "=";
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
  }
  return null;
}

function setCookie(name: string, value: string, days = 7) {
  if (typeof document === 'undefined') return;
  let expires = "";
  if (days) {
    const date = new Date();
    date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
    expires = "; expires=" + date.toUTCString();
  }
  document.cookie = name + "=" + (value || "") + expires + "; path=/; SameSite=Lax";
}

function eraseCookie(name: string) {
  if (typeof document === 'undefined') return;
  document.cookie = name + '=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT; SameSite=Lax';
}

export interface User {
  email: string;
  name: string;
}

const mockSupabaseAuth = {
  async signIn(email: string, password: string): Promise<{ user: User | null; error: string | null }> {
    if (password.length < 6) return { user: null, error: 'Password must be at least 6 characters.' };
    const name = email.split('@')[0];
    const userSession = { email, name: name.charAt(0).toUpperCase() + name.slice(1) };
    setCookie('phoneerp-session', JSON.stringify(userSession), 1);
    return { user: userSession, error: null };
  },
  async signUp(email: string, password: string, name: string): Promise<{ user: User | null; error: string | null }> {
    if (password.length < 6) return { user: null, error: 'Password must be at least 6 characters.' };
    if (!name.trim()) return { user: null, error: 'Name cannot be empty.' };
    const userSession = { email, name: name.trim() };
    setCookie('phoneerp-session', JSON.stringify(userSession), 1);
    return { user: userSession, error: null };
  },
  async signOut(): Promise<{ error: string | null }> {
    eraseCookie('phoneerp-session');
    return { error: null };
  },
  async getUser(): Promise<User | null> {
    const sessionCookie = getCookie('phoneerp-session');
    if (!sessionCookie) return null;
    try {
      return JSON.parse(decodeURIComponent(sessionCookie));
    } catch {
      return null;
    }
  }
};

export const authClient = {
  async signIn(email: string, password: string) {
    if (supabase) {
      const { data, error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) return { user: null, error: error.message };
      const userSession = { email: data.user.email || '', name: data.user.user_metadata?.name || 'User' };
      setCookie('phoneerp-session', JSON.stringify(userSession), 1);
      return { user: userSession, error: null };
    }
    return mockSupabaseAuth.signIn(email, password);
  },
  async signUp(email: string, password: string, name: string) {
    if (supabase) {
      const { data, error } = await supabase.auth.signUp({ email, password, options: { data: { name } } });
      if (error) return { user: null, error: error.message };
      const userSession = { email: data.user?.email || '', name };
      setCookie('phoneerp-session', JSON.stringify(userSession), 1);
      return { user: userSession, error: null };
    }
    return mockSupabaseAuth.signUp(email, password, name);
  },
  async signOut() {
    if (supabase) {
      const { error } = await supabase.auth.signOut();
      eraseCookie('phoneerp-session');
      if (error) return { error: error.message };
      return { error: null };
    }
    return mockSupabaseAuth.signOut();
  },
  async getUser() {
    if (supabase) {
      const { data } = await supabase.auth.getUser();
      if (data.user) {
        return { email: data.user.email || '', name: data.user.user_metadata?.name || 'User' };
      }
      return null;
    }
    return mockSupabaseAuth.getUser();
  }
};
