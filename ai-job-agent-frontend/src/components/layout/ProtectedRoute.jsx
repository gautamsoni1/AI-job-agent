import { Navigate, Outlet, useLocation } from "react-router-dom";
import useAuthStore from "../../store/authStore";

const ProtectedRoute = () => {
  const token = useAuthStore((state) => state.token);
  const bootstrapped = useAuthStore((state) => state.bootstrapped);
  const location = useLocation();

  if (!token) return <Navigate to="/login" replace state={{ from: location }} />;
  if (!bootstrapped) return <div className="grid min-h-screen place-items-center bg-slate-50 text-slate-500">Loading workspace...</div>;
  return <Outlet />;
};

export default ProtectedRoute;
