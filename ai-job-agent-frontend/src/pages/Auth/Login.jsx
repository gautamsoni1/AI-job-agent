import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { authApi } from "../../api/auth";
import useAuthStore from "../../store/authStore";
import { showToast } from "../../store/toastStore";
import AuthLayout, { Input, PrimaryButton } from "./AuthLayout";

const Login = () => {
  const navigate = useNavigate();
  const { setTokens, setUser } = useAuthStore();
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    const payload = { email: form.email.trim(), password: form.password };
    if (!payload.email || !payload.password) return showToast("Enter email and password.", "warning");
    setLoading(true);
    try {
      const tokens = await authApi.login(payload);
      setTokens(tokens);
      const user = await authApi.me();
      setUser(user);
      showToast("Login successful", "success");
      navigate("/dashboard");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Use your AI Job Agent account to continue."
      footer={<><Link className="font-medium text-[#1F4E79]" to="/forgot-password">Forgot password?</Link><span className="mx-2">.</span><Link className="font-medium text-[#1F4E79]" to="/register">Create account</Link></>}
    >
      <form className="space-y-4" onSubmit={submit}>
        <Input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        <Input type="password" placeholder="Password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        <PrimaryButton disabled={loading}>{loading ? "Signing in..." : "Sign in"}</PrimaryButton>
      </form>
    </AuthLayout>
  );
};

export default Login;
