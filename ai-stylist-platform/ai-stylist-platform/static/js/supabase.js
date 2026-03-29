import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm";

const SUPABASE_URL =
  window.__SUPABASE_CONFIG__?.url ||
  window.__SUPABASE_URL__ ||
  "https://uwvgnalhhkqrxlimaseg.supabase.co";

const SUPABASE_ANON_KEY =
  window.__SUPABASE_CONFIG__?.anonKey ||
  window.__SUPABASE_ANON_KEY__ ||
  "sb_publishable_ET8sz43OsKvJBjPrv-REtw_uqOf322A";

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  throw new Error("Supabase URL and anon key must be configured before loading supabase.js");
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

export function getSupabaseConfig() {
  return {
    url: SUPABASE_URL,
    anonKey: SUPABASE_ANON_KEY,
  };
}
