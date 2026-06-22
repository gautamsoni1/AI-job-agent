import { create } from "zustand";

const useAuthStore = create((set) => ({
  user: null,
  token: localStorage.getItem("access_token"),

  setUser: (user) => set({ user }),

  setToken: (token) =>
    set(() => {
      localStorage.setItem("access_token", token);

      return { token };
    }),

  logout: () => {
    localStorage.clear();

    set({
      user: null,
      token: null,
    });
  },
}));

export default useAuthStore;