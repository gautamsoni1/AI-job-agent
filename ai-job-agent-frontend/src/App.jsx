import { useEffect } from "react";
import { authApi } from "./api/auth";
import ToastViewport from "./components/common/ToastViewport";
import AppRoutes from "./routes/AppRoutes";
import useAuthStore from "./store/authStore";

function App() {
  const { token, setUser, setBootstrapped, logout } = useAuthStore();

  useEffect(() => {
    if (!token) {
      setBootstrapped(true);
      return;
    }

    authApi
      .me({ silent: true })
      .then(setUser)
      .catch(() => {
        logout();
        setBootstrapped(true);
      });
  }, [token, setUser, setBootstrapped, logout]);

  return (
    <>
      <AppRoutes />
      <ToastViewport />
    </>
  );
}

export default App;
