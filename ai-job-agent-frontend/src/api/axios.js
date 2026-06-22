import axios from "axios";
import { API_BASE_URL, REFRESH_TOKEN_KEY, TOKEN_KEY } from "../utils/constants";
import useAuthStore from "../store/authStore";
import { showToast } from "../store/toastStore";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

let refreshPromise = null;

const saveTokens = (tokens) => {
  if (tokens?.access_token) localStorage.setItem(TOKEN_KEY, tokens.access_token);
  if (tokens?.refresh_token) localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  useAuthStore.getState().setTokens(tokens);
};

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const message =
      error.response?.data?.error?.message ||
      error.response?.data?.message ||
      error.message ||
      "Something went wrong";

    if (status === 401 && !original?._retry) {
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (refreshToken) {
        original._retry = true;
        refreshPromise ||= axios
          .post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken })
          .then((res) => {
            saveTokens(res.data);
            return res.data.access_token;
          })
          .finally(() => {
            refreshPromise = null;
          });

        try {
          const accessToken = await refreshPromise;
          original.headers.Authorization = `Bearer ${accessToken}`;
          return api(original);
        } catch {
          useAuthStore.getState().logout();
          window.location.assign("/login");
        }
      }

      useAuthStore.getState().logout();
      window.location.assign("/login");
    }

    if (!original?.silent) showToast(message, "danger");
    return Promise.reject(error);
  }
);

export default api;
