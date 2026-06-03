import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Delete, Lock, User } from "lucide-react";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";

export default function Login() {
    const [pin, setPin] = useState("");
    const [err, setErr] = useState(null);
    const [busy, setBusy] = useState(false);
    const { loginWithPin } = useAuth();
    const navigate = useNavigate();

    const submit = async (next) => {
        setBusy(true);
        setErr(null);
        try {
            await loginWithPin(next);
            navigate("/home");
        } catch {
            setErr("Invalid PIN. Try again.");
            setPin("");
        } finally {
            setBusy(false);
        }
    };

    const press = (d) => {
        if (busy) return;
        const next = (pin + d).slice(0, 4);
        setPin(next);
        if (next.length === 4) submit(next);
    };
    const back = () => setPin((p) => p.slice(0, -1));
    const clear = () => setPin("");

    return (
        <div className="bg-jp grid min-h-screen place-items-center px-4 py-8">
            <div className="w-full max-w-md">
                <div className="mb-10 flex justify-center">
                    <Logo size={36} />
                </div>

                <div className="rounded-3xl border border-slate-200/70 bg-white/80 p-8 shadow-[0_20px_60px_rgba(15,23,42,0.06)] backdrop-blur-xl">
                    <div className="flex flex-col items-center">
                        <div className="grid h-16 w-16 place-items-center rounded-full bg-orange-100/80 ring-8 ring-orange-50/60">
                            <User className="text-[#FF6B35]" size={28} />
                        </div>
                        <h1 className="mt-5 font-display text-3xl font-semibold tracking-tight text-slate-900">
                            Enter Owner PIN
                        </h1>
                        <p className="mt-1 text-sm text-slate-500">
                            Sign in to your AI COO dashboard
                        </p>

                        {/* dots */}
                        <div className="mt-8 flex items-center gap-4">
                            {[0, 1, 2, 3].map((i) => (
                                <div
                                    key={i}
                                    className={`h-3.5 w-3.5 rounded-full border-2 transition-all ${
                                        pin.length > i
                                            ? "scale-110 border-[#FF6B35] bg-[#FF6B35]"
                                            : "border-slate-300"
                                    }`}
                                />
                            ))}
                        </div>

                        {err && (
                            <div
                                data-testid={TID.pinError}
                                className="mt-4 text-sm font-medium text-red-500"
                            >
                                {err}
                            </div>
                        )}
                    </div>

                    {/* keypad */}
                    <div className="mt-8 grid grid-cols-3 gap-3">
                        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
                            <button
                                key={n}
                                data-testid={TID.pinDigit(n)}
                                onClick={() => press(String(n))}
                                className="flex h-16 items-center justify-center rounded-2xl bg-white text-2xl font-medium text-slate-900 shadow-[0_2px_8px_rgba(15,23,42,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-md active:scale-95"
                            >
                                {n}
                            </button>
                        ))}
                        <button
                            data-testid={TID.pinClear}
                            onClick={clear}
                            className="flex h-16 items-center justify-center rounded-2xl text-slate-400 hover:bg-slate-100"
                        >
                            <span className="text-sm font-medium">Clear</span>
                        </button>
                        <button
                            data-testid={TID.pinDigit(0)}
                            onClick={() => press("0")}
                            className="flex h-16 items-center justify-center rounded-2xl bg-white text-2xl font-medium text-slate-900 shadow-[0_2px_8px_rgba(15,23,42,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-md active:scale-95"
                        >
                            0
                        </button>
                        <button
                            data-testid={TID.pinBackspace}
                            onClick={back}
                            className="flex h-16 items-center justify-center rounded-2xl text-slate-500 hover:bg-slate-100"
                        >
                            <Delete size={20} />
                        </button>
                    </div>

                    <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-400">
                        <Lock size={12} />
                        <span>Hint: demo PIN is 1234</span>
                    </div>
                </div>

                <p className="mt-6 text-center text-xs uppercase tracking-[0.25em] text-slate-400">
                    Ask Your Restaurant Anything
                </p>
            </div>
        </div>
    );
}
