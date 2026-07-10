import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2, Lock } from "lucide-react";
import Logo from "@/components/Logo";
import PinPad from "@/components/PinPad";
import { TID } from "@/constants/testIds";

// Shown on a returning visit when the Firebase session is still valid but the
// app is "locked". Correct PIN → unlock (POST /me/pin/verify). If the session
// has expired the backend returns 401 and we fall back to full login. "Forgot
// PIN" also drops the session and returns to full login.
export default function PinLock() {
    const { verifyPin, forgotPin, profile } = useAuth();
    const navigate = useNavigate();
    const [pin, setPin] = useState("");
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState(null);

    const submit = async () => {
        if (pin.length < 4) return;
        setBusy(true);
        setErr(null);
        try {
            await verifyPin(pin);
            navigate("/home");
        } catch (e) {
            if (e.code === "expired") {
                // Session gone — context already logged out; go to full login.
                navigate("/");
                return;
            }
            // Only claim the PIN is wrong when the server actually said so.
            setErr(
                e.code === "wrong"
                    ? "Incorrect PIN. Try again."
                    : "Couldn’t reach the server. Please try again."
            );
            setPin("");
        } finally {
            setBusy(false);
        }
    };

    const forgot = async () => {
        setBusy(true);
        await forgotPin();
        navigate("/");
    };

    const who = profile?.name || profile?.restaurant_name;

    return (
        <div className="bg-jp grid min-h-screen place-items-center px-4 py-8">
            <div className="w-full max-w-md">
                <div className="mb-8 flex justify-center">
                    <Logo size={36} />
                </div>
                <div className="rounded-3xl border border-slate-200/70 bg-white/80 p-8 shadow-[0_20px_60px_rgba(15,23,42,0.06)] backdrop-blur-xl">
                    <div className="flex flex-col items-center">
                        <div className="grid h-16 w-16 place-items-center rounded-full bg-orange-100/80 ring-8 ring-orange-50/60">
                            <Lock className="text-[#FF6B35]" size={24} />
                        </div>
                        <h1 className="mt-5 font-display text-3xl font-semibold tracking-tight text-slate-900">
                            Enter your PIN
                        </h1>
                        <p className="mt-1 text-center text-sm text-slate-500">
                            {who ? `Welcome back, ${who}.` : "Welcome back."}
                        </p>
                    </div>

                    <div className="mt-8">
                        <PinPad
                            value={pin}
                            onChange={setPin}
                            disabled={busy}
                            testidDigit={TID.unlockDigit}
                        />
                    </div>

                    {err && (
                        <div
                            data-testid={TID.unlockError}
                            className="mt-4 text-center text-sm font-medium text-red-500"
                        >
                            {err}
                        </div>
                    )}

                    <button
                        data-testid={TID.unlockSubmit}
                        onClick={submit}
                        disabled={busy || pin.length < 4}
                        className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#FF6B35] px-4 py-3 font-medium text-white shadow-sm transition hover:brightness-105 active:scale-[0.99] disabled:opacity-50"
                    >
                        {busy && <Loader2 className="animate-spin" size={16} />}
                        Unlock
                    </button>

                    <button
                        type="button"
                        data-testid={TID.unlockForgot}
                        onClick={forgot}
                        disabled={busy}
                        className="mt-3 w-full text-center text-sm text-slate-500 hover:text-slate-700"
                    >
                        Forgot PIN? Sign in again
                    </button>
                </div>
            </div>
        </div>
    );
}
