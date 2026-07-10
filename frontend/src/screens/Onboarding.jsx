import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2, Store } from "lucide-react";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";

// Shown right after a Firebase sign-in when the profile is missing details the
// token can't provide (name, restaurant_name, and the "other" contact). Saved
// via PATCH /me.
export default function Onboarding() {
    const { profile, updateProfile, logout } = useAuth();
    const navigate = useNavigate();

    // Escape hatch back to the login screen — e.g. a restored session landed
    // here but the user wants to sign in (or register) with a different account.
    const backToLogin = async () => {
        await logout();
        navigate("/");
    };

    // Phone users have no email yet, and vice-versa — ask for whichever is missing.
    const missingContact = profile?.email ? "phone_number" : "email";

    const [name, setName] = useState(profile?.name || "");
    const [restaurant, setRestaurant] = useState(profile?.restaurant_name || "");
    const [contact, setContact] = useState("");
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState(null);

    const submit = async (e) => {
        e.preventDefault();
        setBusy(true);
        setErr(null);
        try {
            const fields = { name, restaurant_name: restaurant };
            if (contact.trim()) fields[missingContact] = contact.trim();
            await updateProfile(fields);
            navigate("/home");
        } catch (ex) {
            setErr(ex?.response?.data?.detail || "Couldn’t save. Please try again.");
        } finally {
            setBusy(false);
        }
    };

    const inputCls =
        "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-[#FF6B35] focus:ring-2 focus:ring-orange-100";

    return (
        <div className="bg-jp grid min-h-screen place-items-center px-4 py-8">
            <div className="w-full max-w-md">
                <div className="mb-8 flex justify-center">
                    <Logo size={36} />
                </div>
                <div className="rounded-3xl border border-slate-200/70 bg-white/80 p-8 shadow-[0_20px_60px_rgba(15,23,42,0.06)] backdrop-blur-xl">
                    <div className="flex flex-col items-center">
                        <div className="grid h-16 w-16 place-items-center rounded-full bg-orange-100/80 ring-8 ring-orange-50/60">
                            <Store className="text-[#FF6B35]" size={26} />
                        </div>
                        <h1 className="mt-5 font-display text-3xl font-semibold tracking-tight text-slate-900">
                            Tell us about you
                        </h1>
                        <p className="mt-1 text-center text-sm text-slate-500">
                            A couple details to set up your dashboard.
                        </p>
                    </div>

                    <form onSubmit={submit} className="mt-6 space-y-3">
                        <input
                            data-testid={TID.onboardName}
                            required
                            placeholder="Your name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className={inputCls}
                        />
                        <input
                            data-testid={TID.onboardRestaurant}
                            required
                            placeholder="Restaurant name"
                            value={restaurant}
                            onChange={(e) => setRestaurant(e.target.value)}
                            className={inputCls}
                        />
                        <input
                            data-testid={TID.onboardContact}
                            type={missingContact === "email" ? "email" : "tel"}
                            placeholder={
                                missingContact === "email"
                                    ? "Email (optional)"
                                    : "Phone, +country code (optional)"
                            }
                            value={contact}
                            onChange={(e) => setContact(e.target.value)}
                            className={inputCls}
                        />
                        {err && (
                            <div className="text-sm font-medium text-red-500">{err}</div>
                        )}
                        <button
                            data-testid={TID.onboardSubmit}
                            type="submit"
                            disabled={busy}
                            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#FF6B35] px-4 py-3 font-medium text-white shadow-sm transition hover:brightness-105 active:scale-[0.99] disabled:opacity-60"
                        >
                            {busy && <Loader2 className="animate-spin" size={16} />}
                            Continue
                        </button>
                        <button
                            type="button"
                            onClick={backToLogin}
                            disabled={busy}
                            className="w-full text-center text-sm text-slate-500 hover:text-slate-700"
                        >
                            Not you? Sign in to a different account
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
