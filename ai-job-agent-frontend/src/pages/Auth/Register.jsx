import { Link } from "react-router-dom";
import { useState } from "react";
import { authApi } from "../../api/auth";
import { showToast } from "../../store/toastStore";
import AuthLayout, { Input, PrimaryButton } from "./AuthLayout";

const Register = () => {
  const [done, setDone] = useState(false);
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", phone: "", password: "" });

  const submit = async (event) => {
    event.preventDefault();
    if (form.password.length < 8) return showToast("Password must be at least 8 characters", "warning");
    const res = await authApi.register(form);
    showToast(res.message || "Account created. Check your email.", "success");
    setDone(true);
  };

  return (
    <AuthLayout title="Create account" subtitle="Start with your basic profile." footer={<Link className="font-medium text-[#1F4E79]" to="/login">Already have an account? Sign in</Link>}>
      {done ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">Account created. Please check your email to verify before running the full pipeline.</div>
      ) : (
        <form className="space-y-4" onSubmit={submit}>
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="First name" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
            <Input placeholder="Last name" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
          </div>
          <Input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <Input placeholder="Phone optional" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
          <Input type="password" placeholder="Password, min 8 chars" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          <PrimaryButton>Create account</PrimaryButton>
        </form>
      )}
    </AuthLayout>
  );
};

export default Register;
