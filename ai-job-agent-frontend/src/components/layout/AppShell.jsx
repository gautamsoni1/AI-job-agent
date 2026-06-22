import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

const AppShell = () => (
  <div className="flex min-h-screen bg-slate-50">
    <Sidebar />
    <div className="min-w-0 flex-1">
      <Topbar />
      <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  </div>
);

export default AppShell;
