import { Link } from "react-router-dom";
import { useState } from "react";
import { authApi } from "../../api/auth";
import { showToast } from "../../store/toastStore";
import AuthLayout, { Input, PrimaryButton } from "./AuthLayout";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    const res = await authApi.forgotPassword({ email });
    showToast(res.message || "If registered, a reset email has been sent.", "success");
  };
  return (
    <AuthLayout title="Reset your password" subtitle="Enter your email and we will send reset instructions." footer={<Link className="font-medium text-[#1F4E79]" to="/login">Back to login</Link>}>
      <form className="space-y-4" onSubmit={submit}>
        <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <PrimaryButton>Send reset link</PrimaryButton>
      </form>
    </AuthLayout>
  );
};

export default ForgotPassword;
