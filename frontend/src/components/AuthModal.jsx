// AuthModal — the single sign-in / sign-up surface for JHAX-COO-AI.
//
// Standalone + reusable: render it anywhere and control it with `open` / `onClose`.
//   <AuthModal open={show} onClose={() => setShow(false)} />
//
// It reuses the existing auth primitives on the AuthContext (Firebase email +
// Google, Twilio Verify phone OTP). It does NOT use the old PIN flow — that has
// been commented out. On a successful sign-in the app's route guards
// (GuestOnly/Protected) take over and move the user into the dashboard, so the
// modal just needs auth to succeed; it also calls onClose().
import { useState } from "react";
import { toast } from "sonner";
import { X, ArrowLeft, Phone, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { TID } from "@/constants/testIds";

// Firebase auth error codes → friendly copy (mirrors the old Login screen).
function friendly(e) {
    const c = e?.code || "";
    if (c.includes("invalid-credential") || c.includes("wrong-password"))
        return "Incorrect email or password.";
    if (c.includes("email-already-in-use")) return "Incorrect password for this account.";
    if (c.includes("weak-password")) return "Password should be at least 6 characters.";
    if (c.includes("invalid-email")) return "That email address looks invalid.";
    if (c.includes("invalid-phone-number")) return "Enter a valid phone in +country format.";
    if (c.includes("too-many-requests")) return "Too many attempts. Try again later.";
    if (c.includes("invalid-verification-code")) return "That code is incorrect.";
    if (c.includes("popup-closed-by-user") || c.includes("cancelled-popup-request"))
        return "Google sign-in was cancelled.";
    if (c.includes("operation-not-allowed"))
        return "This sign-in method isn’t enabled in Firebase yet.";
    return e?.message || "Something went wrong. Try again.";
}

// --- Brand icons (lucide has no Google/Apple marks, so inline SVGs) ---
function GoogleIcon() {
    return (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1Z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z" />
            <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38Z" />
        </svg>
    );
}
function AppleIcon() {
    return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M16.37 12.72c.02 2.5 2.19 3.33 2.21 3.34-.02.06-.35 1.2-1.15 2.37-.69 1.02-1.41 2.03-2.55 2.05-1.11.02-1.47-.66-2.75-.66-1.28 0-1.68.64-2.73.68-1.1.04-1.94-1.1-2.64-2.11-1.42-2.07-2.51-5.85-1.05-8.4a4.07 4.07 0 0 1 3.44-2.1c1.08-.02 2.1.73 2.76.73.66 0 1.9-.9 3.2-.77.54.02 2.07.22 3.05 1.66-.08.05-1.82 1.07-1.8 3.18ZM14.3 4.6c.58-.71.98-1.7.87-2.68-.84.03-1.86.56-2.47 1.27-.54.62-1.02 1.62-.89 2.58.94.07 1.9-.47 2.49-1.17Z" />
        </svg>
    );
}

// Bordered pill (Google / Apple / phone).
function ProviderButton({ icon, label, onClick, disabled, note, testid }) {
    return (
        <button
            type="button"
            data-testid={testid}
            onClick={onClick}
            disabled={disabled}
            className="flex w-full items-center justify-center gap-3 rounded-full border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-900 transition hover:bg-slate-50 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-50"
        >
            {icon}
            <span>{label}</span>
            {note && <span className="text-xs font-normal text-slate-400">{note}</span>}
        </button>
    );
}

// ChatGPT-style clean sans-serif stack, applied across the whole modal so the
// title, subtitle, inputs, and buttons all render in the same font.
const SANS =
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';

const inputCls =
    "w-full rounded-full border border-slate-200 bg-white px-5 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-[#FF6B35] focus:ring-2 focus:ring-orange-100";
// Full-width dark primary CTA (the design's "black Continue"; slate-900 is the
// dashboard's --jp-text token, so it stays on-palette).
const primaryCls =
    "flex w-full items-center justify-center gap-2 rounded-full bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 active:scale-[0.99] disabled:opacity-60";

export default function AuthModal({ open, onClose }) {
    const {
        loginWithEmail,
        registerWithEmail,
        loginWithGoogle,
        sendPhoneOtp,
        verifyPhoneOtp,
    } = useAuth();

    const [panel, setPanel] = useState("main"); // "main" | "phone"
    const [busy, setBusy] = useState(null); // which action is in flight
    const [err, setErr] = useState(null);

    // email
    const [email, setEmail] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [password, setPassword] = useState("");

    // phone
    const [phone, setPhone] = useState("");
    const [code, setCode] = useState("");
    const [codeSent, setCodeSent] = useState(false);

    if (!open) return null;

    const done = () => onClose && onClose();

    const doGoogle = async () => {
        setBusy("google");
        setErr(null);
        try {
            await loginWithGoogle();
            done();
        } catch (ex) {
            setErr(friendly(ex));
        } finally {
            setBusy(null);
        }
    };

    // Email: first Continue reveals the password field; second Continue tries to
    // sign in, and if the account doesn't exist yet, registers it.
    const doEmail = async (e) => {
        e.preventDefault();
        if (!showPassword) {
            setShowPassword(true);
            setErr(null);
            return;
        }
        setBusy("email");
        setErr(null);
        try {
            await loginWithEmail(email.trim(), password);
            done();
        } catch (ex) {
            const c = ex?.code || "";
            if (c.includes("invalid-credential") || c.includes("user-not-found")) {
                // No such account → create one with the entered password.
                try {
                    await registerWithEmail(email.trim(), password);
                    done();
                    return;
                } catch (ex2) {
                    setErr(friendly(ex2));
                }
            } else {
                setErr(friendly(ex));
            }
        } finally {
            setBusy(null);
        }
    };

    const doSendOtp = async (e) => {
        e.preventDefault();
        setBusy("otp-send");
        setErr(null);
        try {
            await sendPhoneOtp(phone.trim());
            setCodeSent(true);
            toast.success(`Code sent to ${phone.trim()}`);
        } catch (ex) {
            setErr(ex?.response?.data?.detail || friendly(ex));
        } finally {
            setBusy(null);
        }
    };

    const doVerifyOtp = async (e) => {
        e.preventDefault();
        setBusy("otp-verify");
        setErr(null);
        try {
            await verifyPhoneOtp(phone.trim(), code.trim());
            done();
        } catch (ex) {
            setErr(ex?.response?.data?.detail || friendly(ex));
        } finally {
            setBusy(null);
        }
    };

    const backToMain = () => {
        setPanel("main");
        setErr(null);
        setCodeSent(false);
        setCode("");
    };

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
            onClick={done}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-label="Log in or sign up"
                style={{ fontFamily: SANS }}
                className="relative w-full max-w-sm rounded-3xl border border-slate-200/70 bg-white p-8 shadow-[0_20px_60px_rgba(15,23,42,0.18)] [&_button]:[font-family:inherit] [&_input]:[font-family:inherit]"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Close */}
                <button
                    type="button"
                    aria-label="Close"
                    data-testid="auth-modal-close"
                    onClick={done}
                    className="absolute right-4 top-4 grid h-8 w-8 place-items-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                >
                    <X size={18} />
                </button>

                {/* Header */}
                <div className="mb-6 text-center">
                    <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
                        Log in or sign up
                    </h2>
                    <p className="mt-1 text-sm text-slate-500">
                        Access your JHAX AI COO dashboard
                    </p>
                </div>

                {err && (
                    <div
                        data-testid={TID.authError}
                        className="mb-4 rounded-2xl bg-red-50 px-4 py-2.5 text-center text-sm font-medium text-red-600"
                    >
                        {err}
                    </div>
                )}

                {panel === "main" && (
                    <>
                        <div className="space-y-3">
                            <ProviderButton
                                testid="auth-google"
                                icon={busy === "google" ? <Loader2 className="animate-spin" size={18} /> : <GoogleIcon />}
                                label="Continue with Google"
                                onClick={doGoogle}
                                disabled={!!busy}
                            />
                            <ProviderButton
                                testid="auth-apple"
                                icon={<AppleIcon />}
                                label="Continue with Apple"
                                note="soon"
                                disabled
                            />
                            <ProviderButton
                                testid="auth-phone"
                                icon={<Phone size={18} />}
                                label="Continue with phone"
                                onClick={() => {
                                    setPanel("phone");
                                    setErr(null);
                                }}
                                disabled={!!busy}
                            />
                        </div>

                        {/* OR divider */}
                        <div className="my-5 flex items-center gap-3">
                            <span className="h-px flex-1 bg-slate-200" />
                            <span className="text-xs font-medium uppercase tracking-widest text-slate-400">or</span>
                            <span className="h-px flex-1 bg-slate-200" />
                        </div>

                        {/* Email + password */}
                        <form onSubmit={doEmail} className="space-y-3">
                            <input
                                data-testid={TID.authEmailInput}
                                type="email"
                                required
                                autoComplete="email"
                                placeholder="Email address"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className={inputCls}
                            />
                            {showPassword && (
                                <input
                                    data-testid={TID.authPasswordInput}
                                    type="password"
                                    required
                                    autoComplete="current-password"
                                    placeholder="Password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className={inputCls}
                                />
                            )}
                            <button
                                data-testid={TID.authEmailSubmit}
                                type="submit"
                                disabled={busy === "email"}
                                className={primaryCls}
                            >
                                {busy === "email" && <Loader2 className="animate-spin" size={16} />}
                                Continue
                            </button>
                        </form>
                    </>
                )}

                {panel === "phone" && (
                    <div>
                        <button
                            type="button"
                            onClick={backToMain}
                            className="mb-3 flex items-center gap-1 text-sm text-slate-500 transition hover:text-slate-700"
                        >
                            <ArrowLeft size={15} /> Back
                        </button>

                        {!codeSent ? (
                            <form onSubmit={doSendOtp} className="space-y-3">
                                <input
                                    data-testid={TID.authPhoneInput}
                                    type="tel"
                                    required
                                    placeholder="+1 555 123 4567"
                                    value={phone}
                                    onChange={(e) => setPhone(e.target.value)}
                                    className={inputCls}
                                />
                                <p className="px-2 text-xs text-slate-400">
                                    Include your country code, e.g. +1 for the US.
                                </p>
                                <button
                                    data-testid={TID.authPhoneSendOtp}
                                    type="submit"
                                    disabled={busy === "otp-send"}
                                    className={primaryCls}
                                >
                                    {busy === "otp-send" && <Loader2 className="animate-spin" size={16} />}
                                    Send code
                                </button>
                            </form>
                        ) : (
                            <form onSubmit={doVerifyOtp} className="space-y-3">
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
                                <button
                                    data-testid={TID.authOtpVerify}
                                    type="submit"
                                    disabled={busy === "otp-verify"}
                                    className={primaryCls}
                                >
                                    {busy === "otp-verify" && <Loader2 className="animate-spin" size={16} />}
                                    Verify &amp; continue
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setCodeSent(false);
                                        setCode("");
                                        setErr(null);
                                    }}
                                    className="w-full text-center text-sm text-slate-500 transition hover:text-slate-700"
                                >
                                    Use a different number
                                </button>
                            </form>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
