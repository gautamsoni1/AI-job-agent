import { create } from "zustand";

let id = 0;

export const useToastStore = create((set) => ({
  toasts: [],
  addToast: (message, type = "info") => {
    const toast = { id: ++id, message, type };
    set((state) => ({ toasts: [...state.toasts, toast] }));
    window.setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((item) => item.id !== toast.id) }));
    }, 4200);
  },
  removeToast: (toastId) =>
    set((state) => ({ toasts: state.toasts.filter((toast) => toast.id !== toastId) })),
}));

export const showToast = (message, type) => useToastStore.getState().addToast(message, type);
