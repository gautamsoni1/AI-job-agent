import { Link } from "react-router-dom";

const AuthLayout = ({ title, subtitle, children, footer }) => (
  <div className="grid min-h-screen place-items-center bg-slate-50 px-4 py-10">
    <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
      <Link to="/login" className="text-lg font-semibold text-slate-950">AI Job Agent</Link>
      <h1 className="mt-8 text-2xl font-semibold text-slate-950">{title}</h1>
      <p className="mt-2 text-sm text-slate-500">{subtitle}</p>
      <div className="mt-7">{children}</div>
      {footer && <div className="mt-6 border-t border-slate-200 pt-5 text-sm text-slate-500">{footer}</div>}
    </div>
  </div>
);

export const Input = (props) => (
  <input
    {...props}
    className="w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm outline-none focus:border-[#1F4E79] focus:ring-2 focus:ring-blue-100"
  />
);

export const PrimaryButton = ({ children, className = "", ...props }) => (
  <button
    {...props}
    className={`w-full rounded-md bg-[#1F4E79] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#173d61] disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
  >
    {children}
  </button>
);

export default AuthLayout;
