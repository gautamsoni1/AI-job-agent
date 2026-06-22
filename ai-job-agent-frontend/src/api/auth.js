import api from "./axios";

export const authApi = {
  register: (payload) => api.post("/auth/register", payload).then((res) => res.data),
  verifyEmail: (token) => api.get(`/auth/verify-email?token=${encodeURIComponent(token)}`).then((res) => res.data),
  login: (payload) => api.post("/auth/login", payload).then((res) => res.data),
  logout: (refreshToken) => api.post("/auth/logout", { refresh_token: refreshToken }).then((res) => res.data),
  forgotPassword: (payload) => api.post("/auth/forgot-password", payload).then((res) => res.data),
  resetPassword: (payload) => api.post("/auth/reset-password", payload).then((res) => res.data),
  changePassword: (payload) => api.post("/auth/change-password", payload).then((res) => res.data),
  me: (config) => api.get("/auth/me", config).then((res) => res.data),
  updateMe: (payload) => api.put("/auth/me", payload).then((res) => res.data),
};
