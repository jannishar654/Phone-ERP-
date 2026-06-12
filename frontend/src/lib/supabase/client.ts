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

export const mockSupabaseAuth = {
  async signIn(email: string, password: string): Promise<{ user: User | null; error: string | null }> {
    // Simple placeholder validator: any password >= 6 chars is fine
    if (password.length < 6) {
      return { user: null, error: 'Password must be at least 6 characters.' };
    }
    
    // Seed a mock name
    const name = email.split('@')[0];
    const capitalizedName = name.charAt(0).toUpperCase() + name.slice(1);
    
    const userSession = {
      email,
      name: capitalizedName
    };
    
    setCookie('phoneerp-session', JSON.stringify(userSession), 1);
    return { user: userSession, error: null };
  },

  async signUp(email: string, password: string, name: string): Promise<{ user: User | null; error: string | null }> {
    if (password.length < 6) {
      return { user: null, error: 'Password must be at least 6 characters.' };
    }
    if (!name.trim()) {
      return { user: null, error: 'Name cannot be empty.' };
    }

    const userSession = {
      email,
      name: name.trim()
    };

    setCookie('phoneerp-session', JSON.stringify(userSession), 1);
    return { user: userSession, error: null };
  },

  async signOut(): Promise<{ error: string | null }> {
    eraseCookie('phoneerp-session');
    return { error: null };
  },

  getUser(): User | null {
    const sessionCookie = getCookie('phoneerp-session');
    if (!sessionCookie) return null;
    try {
      return JSON.parse(decodeURIComponent(sessionCookie));
    } catch {
      return null;
    }
  }
};
