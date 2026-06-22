import { useEffect, useState } from "react";
import { authApi } from "../../api/auth";
import { endpoints, listResource, mutateResource } from "../../api/resources";
import useAuthStore from "../../store/authStore";
import { showToast } from "../../store/toastStore";

const ProfilePage = () => {
  const { user, setUser } = useAuthStore();
  const [account, setAccount] = useState(user || {});
  const [career, setCareer] = useState({});

  useEffect(() => {
    listResource(endpoints.profile).then(setCareer).catch(() => {});
  }, []);

  const saveAccount = async () => {
    const payload = {
      first_name: account.first_name,
      last_name: account.last_name,
      phone: account.phone,
      experience_years: Number(account.experience_years || 0),
      preferred_roles: String(account.preferred_roles || "").split(",").map((x) => x.trim()).filter(Boolean),
      preferred_locations: String(account.preferred_locations || "").split(",").map((x) => x.trim()).filter(Boolean),
      skills: String(account.skills || "").split(",").map((x) => x.trim()).filter(Boolean),
    };
    const updated = await authApi.updateMe(payload);
    setUser(updated);
    showToast("Account updated", "success");
  };

  const saveCareer = async () => {
    await mutateResource("put", endpoints.profile, career);
    showToast("Career profile updated", "success");
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-semibold text-slate-950">Profile</h2>
        <p className="mt-1 text-sm text-slate-500">Account basics and career profile used by the pipeline.</p>
      </div>
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold text-slate-950">Account info</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {["first_name", "last_name", "phone", "experience_years", "preferred_roles", "preferred_locations", "skills"].map((key) => (
            <input key={key} className="rounded-md border border-slate-300 px-3 py-2.5 text-sm" placeholder={key.replaceAll("_", " ")} value={Array.isArray(account[key]) ? account[key].join(", ") : account[key] || ""} onChange={(e) => setAccount({ ...account, [key]: e.target.value })} />
          ))}
        </div>
        <button className="mt-4 rounded-md bg-[#1F4E79] px-4 py-2 text-sm font-semibold text-white" onClick={saveAccount}>Save account</button>
      </section>
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="font-semibold text-slate-950">Career profile</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {["headline", "summary", "linkedin_url", "github_url", "portfolio_url", "target_role", "target_salary_min", "target_salary_max", "work_type"].map((key) => (
            <input key={key} className="rounded-md border border-slate-300 px-3 py-2.5 text-sm" placeholder={key.replaceAll("_", " ")} value={career[key] || ""} onChange={(e) => setCareer({ ...career, [key]: e.target.value })} />
          ))}
        </div>
        <button className="mt-4 rounded-md bg-[#1F4E79] px-4 py-2 text-sm font-semibold text-white" onClick={saveCareer}>Save career profile</button>
      </section>
    </div>
  );
};

export default ProfilePage;
