import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2, ShieldCheck } from "lucide-react";
import Logo from "@/components/Logo";
import PinPad from "@/components/PinPad";
import { TID } from "@/constants/testIds";

// Shown right after the first successful login (or after "Forgot PIN"). The
// user picks a 4-digit PIN, confirms it, and it's saved hashed via POST /me/pin.
export default function PinSetup() {
    const { setPin } = useAuth();
    const navigate = useNavigate();
    const [step, setStep] = useState("create"); // "create" | "confirm"
    const [pin, setPinValue] = useState("");
    const [confirm, setConfirm] = useState("");
    const [busy, setBusy] = useState(false);
    const [err, setErr] = useState(null);

    const toConfirm = () => {
        if (pin.length < 4) return;
        setErr(null);
        setStep("confirm");
    };

    const save = async () => {
        if (confirm !== pin) {
            setErr("PINs don’t match. Try again.");
            setConfirm("");
            setStep("create");
            setPinValue("");
            return;
        }
        setBusy(true);
        setErr(null);
        try {
            await setPin(pin);
            navigate("/home");
        } catch (e) {
            setErr(e?.response?.data?.detail || "Couldn’t save your PIN. Try again.");
        } finally {
            setBusy(false);
        }
    };

    const creating = step === "create";
    const value = creating ? pin : confirm;
    const setValue = creating ? setPinValue : setConfirm;

    return (
        <div className="bg-jp grid min-h-screen place-items-center px-4 py-8">
            <div className="w-full max-w-md">
                <div className="mb-8 flex justify-center">
                    <Logo size={36} />
                </div>
                <div className="rounded-3xl border border-slate-200/70 bg-white/80 p-8 shadow-[0_20px_60px_rgba(15,23,42,0.06)] backdrop-blur-xl">
                    <div className="flex flex-col items-center">
                        <div className="grid h-16 w-16 place-items-center rounded-full bg-orange-100/80 ring-8 ring-orange-50/60">
                            <ShieldCheck className="text-[#FF6B35]" size={26} />
                        </div>
                        <h1 className="mt-5 font-display text-3xl font-semibold tracking-tight text-slate-900">
                            {creating ? "Create a PIN" : "Confirm your PIN"}
                        </h1>
                        <p className="mt-1 text-center text-sm text-slate-500">
                            {creating
                                ? "Set a 4-digit PIN for faster sign-in next time."
                                : "Re-enter the same PIN to confirm."}
                        </p>
                    </div>

                    <div className="mt-8">
                        <PinPad
                            value={value}
                            onChange={setValue}
                            disabled={busy}
                            testidDigit={TID.setPinDigit}
                        />
                    </div>

                    {err && (
                        <div
                            data-testid={TID.setPinError}
                            className="mt-4 text-center text-sm font-medium text-red-500"
                        >
                            {err}
                        </div>
                    )}

                    <button
                        data-testid={TID.setPinContinue}
                        onClick={creating ? toConfirm : save}
                        disabled={busy || value.length < 4}
                        className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-[#FF6B35] px-4 py-3 font-medium text-white shadow-sm transition hover:brightness-105 active:scale-[0.99] disabled:opacity-50"
                    >
                        {busy && <Loader2 className="animate-spin" size={16} />}
                        {creating ? "Continue" : "Save PIN"}
                    </button>
                </div>
            </div>
        </div>
    );
}
