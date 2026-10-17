import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { Me } from "./api/types";

const safeStorage = createJSONStorage(() => {
  try {
    const k = "__ms_probe";
    localStorage.setItem(k, "1");
    localStorage.removeItem(k);
    return localStorage;
  } catch {
    const mem = new Map<string, string>();
    return {
      getItem: (k: string) => mem.get(k) ?? null,
      setItem: (k: string, v: string) => void mem.set(k, v),
      removeItem: (k: string) => void mem.delete(k),
    };
  }
});

interface AuthState {
  token: string | null;
  user: Me | null;
  setSession: (token: string, user: Me) => void;
  setUser: (user: Me) => void;
  signOut: () => void;
}

export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      signOut: () => set({ token: null, user: null }),
    }),
    { name: "movieswipe-auth", storage: safeStorage },
  ),
);

export type DeckMode = "solo" | "quick" | "mood" | "decompress" | "new";

interface DeckPrefs {
  mode: DeckMode;
  mood: string | null;
  type: "all" | "movie" | "tv";
  language: string;
  blind: boolean;
  seenTutorial: boolean;
  set: (p: Partial<Omit<DeckPrefs, "set">>) => void;
}

export const useDeckPrefs = create<DeckPrefs>()(
  persist(
    (set) => ({
      mode: "solo",
      mood: null,
      type: "all",
      language: "",
      blind: false,
      seenTutorial: false,
      set: (p) => set(p),
    }),
    { name: "movieswipe-deck", storage: safeStorage },
  ),
);

interface ToastState {
  toasts: { id: number; text: string; action?: { label: string; run: () => void } }[];
  push: (text: string, action?: { label: string; run: () => void }) => void;
  dismiss: (id: number) => void;
}

let toastId = 0;
export const useToasts = create<ToastState>()((set) => ({
  toasts: [],
  push: (text, action) => {
    const id = ++toastId;
    set((s) => ({ toasts: [...s.toasts.slice(-2), { id, text, action }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), action ? 5000 : 2600);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export const toast = (text: string, action?: { label: string; run: () => void }) =>
  useToasts.getState().push(text, action);
