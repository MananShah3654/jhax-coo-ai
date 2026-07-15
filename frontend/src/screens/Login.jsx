import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { Mail, Phone, Loader2 } from "lucide-react";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";

// Firebase auth error codes → friendly copy.
function friendly(e) {
    const c = e?.code || "";
    if (c.includes("invalid-credential") || c.includes("wrong-password"))
        return "Incorrect email or password.";
    if (c.includes("user-not-found")) return "No account with that email.";
    if (c.includes("email-already-in-use")) return "That email is already registered.";
    if (c.includes("weak-password")) return "Password should be at least 6 characters.";
    if (c.includes("invalid-email")) return "That email address looks invalid.";
    if (c.includes("invalid-phone-number")) return "Enter a valid phone in +country format.";
    if (c.includes("too-many-requests")) return "Too many attempts. Try again later.";
    if (c.includes("invalid-verification-code")) return "That code is incorrect.";
    if (c.includes("operation-not-allowed")) {
        // Firebase reuses this code for two very different problems. When the
        // message mentions "region", the provider IS enabled but SMS to that
        // phone's country is blocked by the SMS region policy.
        const m = (e?.message || "").toLowerCase();
        if (m.includes("region"))
            return "SMS to this phone number’s country is blocked. In Firebase → Authentication → Settings → SMS region policy, allow the region (e.g. India) and try again.";
        return "This sign-in method isn’t enabled in Firebase yet.";
    }
    if (c.includes("billing-not-enabled") || c.includes("quota"))
        return "SMS quota reached / billing not enabled for phone sign-in. Use a test phone number or upgrade the Firebase plan.";
    return e?.message || "Something went wrong. Try again.";
}

export default function Login() {
    const [tab, setTab] = useState("email");

    return (
        <div className="bg-jp grid min-h-screen place-items-center px-4 py-8">
            <div className="w-full max-w-md">
                <div className="mb-8 flex justify-center">
                    <Logo size={36} />
                </div>

                <div className="rounded-3xl border border-slate-200/70 bg-white/80 p-8 shadow-[0_20px_60px_rgba(15,23,42,0.06)] backdrop-blur-xl">
                    <div className="flex flex-col items-center">
                        <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                            Sign in
                        </h1>
                        <p className="mt-1 text-sm text-slate-500">
                            Access your AI COO dashboard
                        </p>
                    </div>

                    {/* Tabs */}
                    <div className="mt-6 grid grid-cols-2 gap-1 rounded-2xl bg-slate-100/80 p-1">
                        <TabButton
                            active={tab === "email"}
                            onClick={() => setTab("email")}
                            testid={TID.authTabEmail}
                            icon={<Mail size={15} />}
                            label="Email"
                        />
                        <TabButton
                            active={tab === "phone"}
                            onClick={() => setTab("phone")}
                            testid={TID.authTabPhone}
                            icon={<Phone size={15} />}
                            label="Phone"
                        />
                    </div>

                    <div className="mt-6">
                        {tab === "email" ? <EmailForm /> : <PhoneForm />}
                    </div>
                </div>

                <p className="mt-6 text-center text-xs uppercase tracking-[0.25em] text-slate-400">
                    Ask Your Restaurant Anything
                </p>
            </div>
        </div>
    );
}

function TabButton({ active, onClick, testid, icon, label }) {
    return (
        <button
            data-testid={testid}
            onClick={onClick}
            className={`flex items-center justify-center gap-1.5 rounded-xl py-2 text-sm font-medium transition-all ${
                active
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
            }`}
        >
            {icon}
            {label}
        </button>
    );
}

const inputCls =
    "w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition focus:border-[#FF6B35] focus:ring-2 focus:ring-orange-100";
const btnCls =
    "flex w-full items-center justify-center gap-2 rounded-2xl bg-[#FF6B35] px-4 py-3 font-medium text-white shadow-sm transition hover:brightness-105 active:scale-[0.99] disabled:opacity-60";

function EmailForm() {
    const { loginWithEmail, registerWithEmail } = useAuth();
    const navigate = useNavigate();
    const [mode, setMode] = useState("signin"); // or "register"
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState(null);

    // After a failed sign-in we can't tell "wrong password" from "no account"
    // (Firebase returns auth/invalid-credential for both), so we nudge the user
    // toward registering as well.
    const [suggestRegister, setSuggestRegister] = useState(false);

    const submit = async (e) => {
        e.preventDefault();
        setBusy(true);
        setErr(null);
        setSuggestRegister(false);
        try {
            if (mode === "register") await registerWithEmail(email, password);
            else await loginWithEmail(email, password);
            // AuthContext picks up the session; go to app (onboarding if needed).
            navigate("/home");
        } catch (ex) {
            setErr(friendly(ex));
            const c = ex?.code || "";
            if (
                mode === "signin" &&
                (c.includes("invalid-credential") ||
                    c.includes("user-not-found") ||
                    c.includes("wrong-password"))
            ) {
                setSuggestRegister(true);
            }
        } finally {
            setBusy(false);
        }
    };

    return (
        <form onSubmit={submit} className="space-y-3">
            <input
                data-testid={TID.authEmailInput}
                type="email"
                required
                placeholder="you@restaurant.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputCls}
            />
            <input
                data-testid={TID.authPasswordInput}
                type="password"
                required
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputCls}
            />
            {err && (
                <div data-testid={TID.authError} className="text-sm font-medium text-red-500">
                    {err}
                    {suggestRegister && (
                        <>
                            {" "}
                            <button
                                type="button"
                                onClick={() => {
                                    setErr(null);
                                    setSuggestRegister(false);
                                    setMode("register");
                                }}
                                className="font-semibold text-[#FF6B35] underline underline-offset-2"
                            >
                                Create an account instead
                            </button>
                        </>
                    )}
                </div>
            )}
            <button data-testid={TID.authEmailSubmit} type="submit" disabled={busy} className={btnCls}>
                {busy && <Loader2 className="animate-spin" size={16} />}
                {mode === "register" ? "Create account" : "Sign in"}
            </button>
            <button
                type="button"
                data-testid={TID.authRegisterToggle}
                onClick={() => {
                    setErr(null);
                    setSuggestRegister(false);
                    setMode((m) => (m === "register" ? "signin" : "register"));
                }}
                className="w-full text-center text-sm text-slate-500 hover:text-slate-700"
            >
                {mode === "register"
                    ? "Already have an account? Log in"
                    : "Don’t have an account? Register"}
            </button>
        </form>
    );
}

function PhoneForm() {
    const { sendPhoneOtp, verifyPhoneOtp } = useAuth();
    const navigate = useNavigate();
    const [phone, setPhone] = useState("");
    const [code, setCode] = useState("");
    const [codeSent, setCodeSent] = useState(false);
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState(null);

    // Backend (Twilio/Firebase) errors carry a `detail`; a Firebase custom-token
    // sign-in error carries a `code` that friendly() knows how to phrase.
    const errMsg = (ex) => ex?.response?.data?.detail || friendly(ex);

    const send = async (e) => {
        e.preventDefault();
        setBusy(true);
        setErr(null);
        try {
            await sendPhoneOtp(phone.trim());
            setCodeSent(true);
            toast.success(`Code sent to ${phone.trim()}`);
        } catch (ex) {
            setErr(errMsg(ex));
        } finally {
            setBusy(false);
        }
    };

    const verify = async (e) => {
        e.preventDefault();
        setBusy(true);
        setErr(null);
        try {
            await verifyPhoneOtp(phone.trim(), code.trim());
            navigate("/home");
        } catch (ex) {
            setErr(errMsg(ex));
        } finally {
            setBusy(false);
        }
    };

    if (!codeSent) {
        return (
            <form onSubmit={send} className="space-y-3">
                <input
                    data-testid={TID.authPhoneInput}
                    type="tel"
                    required
                    placeholder="+1 555 123 4567"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className={inputCls}
                />
                <p className="px-1 text-xs text-slate-400">
                    Include your country code, e.g. +1 for the US.
                </p>
                {err && (
                    <div data-testid={TID.authError} className="text-sm font-medium text-red-500">
                        {err}
                    </div>
                )}
                <button data-testid={TID.authPhoneSendOtp} type="submit" disabled={busy} className={btnCls}>
                    {busy && <Loader2 className="animate-spin" size={16} />}
                    Send code
                </button>
            </form>
        );
    }

    return (
        <form onSubmit={verify} className="space-y-3">
            <p className="text-sm text-slate-500">
                Enter the 6-digit code sent to <b>{phone}</b>.
            </p>
            <input
                data-testid={TID.authOtpInput}
                inputMode="numeric"
                maxLength={6}
                required
                placeholder="123456"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className={`${inputCls} text-center text-2xl tracking-[0.5em]`}
            />
            {err && (
                <div data-testid={TID.authError} className="text-sm font-medium text-red-500">
                    {err}
                </div>
            )}
            <button data-testid={TID.authOtpVerify} type="submit" disabled={busy} className={btnCls}>
                {busy && <Loader2 className="animate-spin" size={16} />}
                Verify &amp; continue
            </button>
            <button
                type="button"
                onClick={() => {
                    setCodeSent(false);
                    setCode("");
                    setErr(null);
                }}
                className="w-full text-center text-sm text-slate-500 hover:text-slate-700"
            >
                Use a different number
            </button>
        </form>
    );
}
