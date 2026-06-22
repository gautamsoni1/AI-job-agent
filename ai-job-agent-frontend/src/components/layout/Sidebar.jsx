import { NavLink } from "react-router-dom";

const items = [
  ["Dashboard", "/dashboard"],
  ["Pipeline", "/pipeline"],
  ["Resumes", "/resumes"],
  ["ATS Scoring", "/ats"],
  ["Jobs", "/jobs"],
  ["Matching", "/matching"],
  ["Applications", "/applications"],
  ["Cover Letters", "/cover-letters"],
  ["Interview Prep", "/interview-prep"],
  ["Career Coach", "/career"],
  ["Market Intel", "/market"],
  ["Timeline", "/timeline"],
  ["Profile", "/profile"],
  ["Admin", "/admin"],
];

const Sidebar = () => (
  <aside className="hidden w-68 shrink-0 border-r border-slate-200 bg-white lg:block">
    <div className="border-b border-slate-200 px-6 py-5">
      <p className="text-lg font-semibold text-slate-950">AI Job Agent</p>
      <p className="text-xs text-slate-500">Career automation workspace</p>
    </div>
    <nav className="space-y-1 p-3">
      {items.map(([label, to]) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `block rounded-md px-3 py-2 text-sm font-medium ${
              isActive ? "bg-[#1F4E79] text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
            }`
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  </aside>
);

export default Sidebar;
