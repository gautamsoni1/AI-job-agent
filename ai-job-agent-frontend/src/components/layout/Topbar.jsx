import { useNavigate } from "react-router-dom";
import { authApi } from "../../api/auth";
import useAuthStore from "../../store/authStore";
import { showToast } from "../../store/toastStore";

const Topbar = ({ notifications = [] }) => {
  const navigate = useNavigate();
  const { user, refreshToken, logout } = useAuthStore();
  const initials = `${user?.first_name?.[0] || ""}${user?.last_name?.[0] || ""}` || "U";

  const onLogout = async () => {
    try {
      if (refreshToken) await authApi.logout(refreshToken);
    } catch {
      // Local logout still wins if the server cannot be reached.
    }
    logout();
    showToast("Logged out successfully", "success");
    navigate("/login");
  };

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Welcome back</p>
          <h1 className="text-xl font-semibold text-slate-950">{user?.first_name || "Candidate"}</h1>
        </div>
        <div className="flex items-center gap-3">
          <details className="relative">
            <summary className="list-none rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700">
              Notifications {notifications.filter((item) => !item.is_read).length ? `(${notifications.filter((item) => !item.is_read).length})` : ""}
            </summary>
            <div className="absolute right-0 mt-2 w-80 rounded-lg border border-slate-200 bg-white p-2 shadow-lg">
              {notifications.length ? notifications.slice(0, 6).map((item) => (
                <div key={item._id || item.title} className="rounded-md p-3 hover:bg-slate-50">
                  <p className="text-sm font-medium text-slate-950">{item.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.message}</p>
                </div>
              )) : <p className="p-3 text-sm text-slate-500">No notifications yet.</p>}
            </div>
          </details>
          <div className="grid h-10 w-10 place-items-center rounded-full bg-[#1F4E79] text-sm font-semibold text-white">{initials}</div>
          <button className="rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>
      {user && !user.is_verified && (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Please verify your email to unlock the full pipeline. Check your inbox for the verification link.
        </div>
      )}
    </header>
  );
};

export default Topbar;
