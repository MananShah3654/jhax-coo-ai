import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Loader2, Check } from "lucide-react";
import Logo from "@/components/Logo";
import { TID } from "@/constants/testIds";

// Shown once, right after a first-time user sets their PIN. We have no live POS
// integration yet, so picking a provider calls POST /me/connect-pos, which seeds
// a demo dataset (menu, customers, orders, team, shifts) named after the
// restaurant from onboarding. On success we land in the app with data to explore.

// Each POS renders as a branded tile. Logos are inline SVG (no external assets)
// so the bundle stays self-contained; marks are simple emblems in brand colors.
function SquareMark() {
    return (
        <svg viewBox="0 0 40 40" className="h-8 w-8" aria-hidden>
            <rect x="6" y="6" width="28" height="28" rx="7" fill="none" stroke="#fff" strokeWidth="4" />
            <rect x="15" y="15" width="10" height="10" rx="2.5" fill="#fff" />
        </svg>
    );
}
function CloverMark() {
    return (
        <svg viewBox="0 0 40 40" className="h-8 w-8" aria-hidden fill="#fff">
            <circle cx="15" cy="15" r="7" />
            <circle cx="25" cy="15" r="7" />
            <circle cx="15" cy="25" r="7" />
            <circle cx="25" cy="25" r="7" />
        </svg>
    );
}
function ToastMark() {
    return (
        <svg viewBox="0 0 40 40" className="h-8 w-8" aria-hidden>
            <path d="M20 6c-7 0-12 3-12 8 0 2 1 3 3 3v9a4 4 0 0 0 4 4h10a4 4 0 0 0 4-4v-9c2 0 3-1 3-3 0-5-5-8-12-8z" fill="#fff" />
        </svg>
    );
}
function LightspeedMark() {
    return (
        <svg viewBox="0 0 40 40" className="h-8 w-8" aria-hidden>
            <path d="M22 5 10 23h8l-3 12 15-20h-9l3-10z" fill="#fff" />
        </svg>
    );
}
function SpotOnMark() {
    return (
        <svg viewBox="0 0 40 40" className="h-8 w-8" aria-hidden>
            <path d="M20 5c-6 0-11 5-11 11 0 8 11 19 11 19s11-11 11-19c0-6-5-11-11-11z" fill="#fff" />
            <circle cx="20" cy="16" r="4.5" fill="#00B37D" />
        </svg>
    );
}
function ShopifyMark() {
    return (
        <svg viewBox="0 0 40 40" className="h-8 w-8" aria-hidden>
            <path d="M13 11c-2 0-3 1-3 3l-2 16 12 3 12-3-3-17c0-1-1-2-2-2l-3-.4C20 8 18 8 16 10c-1 0-2 .5-3 1z" fill="#fff" />
            <path d="M20 15c-2 0-3 1-3 3s1 2 3 3 2 1 2 2-1 1-2 1-2-.5-3-1" fill="none" stroke="#5E8E3E" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
    );
}

const POS = [
    { id: "square", name: "Square", tagline: "Payments & POS", bg: "#1A1A1A", Mark: SquareMark },
    { id: "clover", name: "Clover", tagline: "Restaurant POS", bg: "#4CAF50", Mark: CloverMark },
    { id: "toast", name: "Toast", tagline: "Restaurant platform", bg: "#FF6A1A", Mark: ToastMark },
    { id: "lightspeed", name: "Lightspeed", tagline: "Retail & dining", bg: "#E4002B", Mark: LightspeedMark },
    { id: "spoton", name: "SpotOn", tagline: "Point of sale", bg: "#00B37D", Mark: SpotOnMark },
    { id: "shopify", name: "Shopify POS", tagline: "Commerce & POS", bg: "#5E8E3E", Mark: ShopifyMark },
];

export default function ConnectPos() {
    const { profile, refreshProfile, logout } = useAuth();
    const navigate = useNavigate();
    const [busy, setBusy] = useState(null); // provider id currently connecting
    const [err, setErr] = useState(null);

    const restaurant = profile?.restaurant_name || "your restaurant";

    const connect = async (provider) => {
        if (busy) return;
        setBusy(provider);
        setErr(null);
        try {
            await api.post("/me/connect-pos", { provider });
            await refreshProfile(); // pos_provider now set → onboarding gate opens
            toast.success("POS connected — your data is ready.");
            navigate("/home");
        } catch (ex) {
            setErr(ex?.response?.data?.detail || "Couldn’t connect. Please try again.");
            setBusy(null);
        }
    };

    const backToLogin = async () => {
        await logout();
        navigate("/");
    };

    return (
        <div className="bg-jp grid min-h-screen place-items-center px-4 py-8">
            <div className="w-full max-w-2xl">
                <div className="mb-8 flex justify-center">
                    <Logo size={36} />
                </div>
                <div className="rounded-3xl border border-slate-200/70 bg-white/80 p-8 shadow-[0_20px_60px_rgba(15,23,42,0.06)] backdrop-blur-xl">
                    <div className="flex flex-col items-center text-center">
                        <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                            Connect your POS
                        </h1>
                        <p className="mt-1 max-w-md text-sm text-slate-500">
                            Choose where <span className="font-medium text-slate-700">{restaurant}</span> takes
                            orders. We’ll pull in your menu, sales, customers and team so your dashboard is
                            ready to explore.
                        </p>
                    </div>

                    <div className="mt-7 grid grid-cols-1 gap-3 sm:grid-cols-2">
                        {POS.map(({ id, name, tagline, bg, Mark }) => {
                            const isBusy = busy === id;
                            const disabled = Boolean(busy) && !isBusy;
                            return (
                                <button
                                    key={id}
                                    data-testid={TID.posTile(id)}
                                    onClick={() => connect(id)}
                                    disabled={Boolean(busy)}
                                    className={`group flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left transition
                                        hover:border-[#FF6B35] hover:shadow-sm active:scale-[0.99]
                                        ${disabled ? "opacity-50" : ""}`}
                                >
                                    <span
                                        className="grid h-14 w-14 shrink-0 place-items-center rounded-xl"
                                        style={{ background: bg }}
                                    >
                                        <Mark />
                                    </span>
                                    <span className="min-w-0 flex-1">
                                        <span className="block font-display text-base font-semibold text-slate-900">
                                            {name}
                                        </span>
                                        <span className="block truncate text-xs text-slate-500">
                                            {tagline}
                                        </span>
                                    </span>
                                    {isBusy ? (
                                        <Loader2 className="animate-spin text-[#FF6B35]" size={18} />
                                    ) : (
                                        <span className="text-slate-300 transition group-hover:text-[#FF6B35]">→</span>
                                    )}
                                </button>
                            );
                        })}
                    </div>

                    {err && (
                        <div data-testid={TID.posError} className="mt-4 text-center text-sm font-medium text-red-500">
                            {err}
                        </div>
                    )}

                    <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-400">
                        <Check size={13} className="text-emerald-500" />
                        No POS keys needed — we’ll load a demo dataset you can replace later.
                    </div>

                    <button
                        type="button"
                        onClick={backToLogin}
                        disabled={Boolean(busy)}
                        className="mt-4 w-full text-center text-sm text-slate-500 hover:text-slate-700 disabled:opacity-60"
                    >
                        Not you? Sign in to a different account
                    </button>
                </div>
            </div>

            {busy && (
                <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/40 backdrop-blur-sm">
                    <div className="flex flex-col items-center gap-3 rounded-2xl bg-white px-8 py-6 shadow-xl">
                        <Loader2 className="animate-spin text-[#FF6B35]" size={28} />
                        <div className="text-sm font-medium text-slate-700">
                            Connecting {POS.find((p) => p.id === busy)?.name}…
                        </div>
                        <div className="text-xs text-slate-400">Preparing your restaurant data</div>
                    </div>
                </div>
            )}
        </div>
    );
}
