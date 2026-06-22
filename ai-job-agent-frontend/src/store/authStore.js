import { create } from "zustand";
import { REFRESH_TOKEN_KEY, TOKEN_KEY } from "../utils/constants";

const useAuthStore = create((set) => ({
  user: null,
  token: localStorage.getItem(TOKEN_KEY),
  refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
  bootstrapped: false,

  setUser: (user) => set({ user, bootstrapped: true }),
  setBootstrapped: (bootstrapped) => set({ bootstrapped }),
  setTokens: (tokens = {}) => {
    if (tokens.access_token) localStorage.setItem(TOKEN_KEY, tokens.access_token);
    if (tokens.refresh_token) localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
    set({
      token: tokens.access_token || localStorage.getItem(TOKEN_KEY),
      refreshToken: tokens.refresh_token || localStorage.getItem(REFRESH_TOKEN_KEY),
    });
  },
  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    set({ user: null, token: null, refreshToken: null, bootstrapped: true });
  },
}));

export default useAuthStore;
