# Static frontend helpers

This folder contains the minimal browser-side Supabase helpers for a plain HTML/CSS frontend.

## Files

- `js/supabase.js` - creates a shared Supabase client
- `js/auth.js` - exposes `signUp`, `signIn`, `signOut`, `getSession`, `getUser`, and `onAuthStateChange`

## Usage

Load them from HTML as ES modules:

```html
<script type="module">
  import { signIn, signUp, getSession } from "./js/auth.js";
</script>
```

## Configuration

You can override the baked-in demo values by defining either:

- `window.__SUPABASE_CONFIG__ = { url, anonKey }`
- `window.__SUPABASE_URL__` and `window.__SUPABASE_ANON_KEY__`
