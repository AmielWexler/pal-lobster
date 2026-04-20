import { useCallback, useEffect, useState } from "react";
import { auth } from "../foundry";

// auth() is callable as a function → Promise<string> (access token)
// auth.getTokenOrUndefined() → string | undefined (sync, no redirect)
// auth.signIn() → triggers OAuth redirect

type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; token: string }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

const DEV_TOKEN = import.meta.env.VITE_DEV_TOKEN as string | undefined;

export function useFoundryAuth() {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    const init = async () => {
      // Local dev bypass: set VITE_DEV_TOKEN in frontend/.env.local to skip OAuth.
      if (DEV_TOKEN) {
        setState({ status: "authenticated", token: DEV_TOKEN });
        return;
      }

      // If we already have a cached token, use it immediately.
      const cached = auth.getTokenOrUndefined();
      if (cached) {
        setState({ status: "authenticated", token: cached });
        return;
      }

      // If the URL contains ?code= we're on the OAuth callback — let the
      // library handle it by calling auth() which processes the code exchange.
      if (window.location.search.includes("code=")) {
        try {
          const token = await auth();
          window.history.replaceState({}, "", window.location.pathname);
          setState({ status: "authenticated", token });
        } catch (e) {
          setState({ status: "error", message: String(e) });
        }
        return;
      }

      setState({ status: "unauthenticated" });
    };

    init();
  }, []);

  // Calling auth() with no cached token triggers the Foundry OAuth redirect.
  const signIn = useCallback(async () => {
    try {
      await auth.signIn();
    } catch (e) {
      setState({ status: "error", message: String(e) });
    }
  }, []);

  // Called after a background token refresh to keep state in sync.
  const refreshToken = useCallback(async () => {
    try {
      const refreshed = await auth.refresh();
      if (refreshed?.access_token) {
        setState({ status: "authenticated", token: refreshed.access_token });
        return refreshed.access_token;
      }
    } catch {
      setState({ status: "unauthenticated" });
    }
    return null;
  }, []);

  return { state, signIn, refreshToken };
}
