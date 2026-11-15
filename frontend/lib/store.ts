import { create } from "zustand";

import type { Snapshot } from "./types";

interface LiveState {
  snapshot: Snapshot | null;
  connected: boolean;
  soundOn: boolean;
  selectedMint: string | null;
  lastEventAt: number;
  setSnapshot: (snapshot: Snapshot) => void;
  setConnected: (connected: boolean) => void;
  setSoundOn: (soundOn: boolean) => void;
  toggleSound: () => void;
  openToken: (mint: string) => void;
  closeToken: () => void;
}

export const useLiveStore = create<LiveState>((set, get) => ({
  snapshot: null,
  connected: false,
  soundOn: false,
  selectedMint: null,
  lastEventAt: 0,
  setSnapshot: (snapshot) => set({ snapshot, lastEventAt: Date.now() }),
  setConnected: (connected) => set({ connected }),
  setSoundOn: (soundOn) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("memeradar:sound", soundOn ? "1" : "0");
    }
    set({ soundOn });
  },
  toggleSound: () => get().setSoundOn(!get().soundOn),
  openToken: (mint) => set({ selectedMint: mint }),
  closeToken: () => set({ selectedMint: null }),
}));
