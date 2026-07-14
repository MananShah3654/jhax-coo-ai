import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    DollarSign,
    ShoppingBag,
    Coins,
    Repeat,
    Users,
    ArrowRight,
    Sun,
    Sparkles,
    Send,
    UtensilsCrossed,
    Receipt,
    ShoppingCart,
    Percent,
    RotateCw,
    Armchair,
} from "lucide-react";
import { api, fmtUsd } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import Layout from "@/components/Layout";
import HealthRing from "@/components/HealthRing";
import KpiTile from "@/components/KpiTile";
import VoiceMic from "@/components/VoiceMic";
import { openShareModal } from "@/components/ShareModal";
import { TID } from "@/constants/testIds";
import { toast } from "sonner";

function Briefing({ data, onLaunch, onShare }) {
    if (!data) return null;
    return (
        <div
            data-testid={TID.briefingCard}
            className="fade-up relative overflow-hidden rounded-3xl border border-slate-200/70 bg-gradient-to-br from-white via-white to-orange-50/40 p-7 shadow-[0_2px_18px_rgba(15,23,42,0.04)]"
        >
            <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-orange-100/60 blur-3xl" />
            <div className="relative flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                <Sun size={14} />
                Daily CEO Briefing
            </div>
            <h2 className="relative mt-2 font-display text-3xl font-semibold tracking-tight text-slate-900">
                Good morning, {data.owner_name}.
            </h2>
            <p className="relative mt-1 max-w-2xl text-[15px] leading-relaxed text-slate-600">
                Yesterday you did{" "}
                <b>{fmtUsd(data.yesterday_revenue)}</b> on{" "}
                <b>{data.yesterday_orders}</b> orders{" "}
                <span
                    className={`font-semibold ${data.growth_pct > 0 ? "text-emerald-600" : "text-red-500"}`}
                >
                    ({data.growth_pct > 0 ? "+" : ""}
                    {data.growth_pct}% DoD)
                </span>
                . Top seller was <b>{data.top_seller}</b>. Best branch was{" "}
                <b>{data.best_branch}</b>.
            </p>

            <div className="relative mt-5 grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-amber-100 bg-amber-50/60 p-4">
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-700">
                        Risk Areas
                    </div>
                    <ul className="mt-1.5 space-y-1 text-sm text-slate-700">
                        {(data.risk_areas || []).map((r, i) => (
                            <li key={i} className="flex gap-2">
                                <span className="text-amber-500">•</span>
                                {r}
                            </li>
                        ))}
                    </ul>
                </div>
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-4">
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700">
                        Recommended Action
                    </div>
                    <p className="mt-1.5 text-sm text-slate-800">
                        {data.recommended_action}
                    </p>
                    <div className="mt-2 font-mono text-lg font-semibold text-emerald-600">
                        +${(data.expected_opportunity || 0).toLocaleString()}/week opportunity
                    </div>
                </div>
            </div>

            <div className="relative mt-5 flex flex-wrap items-center gap-2">
                <button
                    data-testid={TID.briefingLaunchBtn}
                    onClick={onLaunch}
                    className="inline-flex items-center gap-2 rounded-full bg-[#FF6B35] px-5 py-2.5 text-sm font-medium text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:-translate-y-0.5 hover:bg-[#E85D2A]"
                >
                    <Sparkles size={14} /> Launch Campaign
                </button>
                <button
                    data-testid={TID.briefingShareBtn}
                    onClick={onShare}
                    className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
                >
                    <Send size={14} /> Share Report
                </button>
            </div>
        </div>
    );
}

export default function Home() {
    const { auth } = useAuth();
    const navigate = useNavigate();
    const [data, setData] = useState(null);
    const [question, setQuestion] = useState("");

    useEffect(() => {
        api.get("/dashboard").then((r) => setData(r.data));
    }, []);

    const askAnything = (text) => {
        const q = (text || question).trim();
        if (!q) return;
        navigate("/chat", { state: { question: q } });
    };

    const onTranscribed = (text) => {
        if (text && text.trim()) {
            askAnything(text.trim());
        }
    };

    const onLaunch = () => {
        // Open Marketing prefilled with the at-risk reactivation flow
        try {
            sessionStorage.setItem(
                "campaign_prefill",
                JSON.stringify({
                    audience: "at_risk",
                    channel: "sms",
                    goal: "Reactivate inactive customers",
                })
            );
        } catch {}
        navigate("/marketing");
    };
    const onShare = () => openShareModal("daily");

    if (!data)
        return (
            <Layout>
                <div className="flex h-[60vh] items-center justify-center text-slate-400">
                    Loading your restaurant…
                </div>
            </Layout>
        );

    const t = data.today;
    return (
        <Layout>
            {/* Hero */}
            <div className="grid items-start gap-8 lg:grid-cols-[1fr_280px]">
                <div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                        {auth?.owner?.restaurant} · AI COO
                    </div>
                    <h1 className="mt-2 font-display text-4xl font-semibold tracking-tight text-slate-900 md:text-5xl">
                        Ask your restaurant anything.
                    </h1>
                    <p className="mt-2 max-w-xl text-[15px] text-slate-500">
                        One question. One answer. One action — straight from
                        your data.
                    </p>

                    {/* Ask Anything bar */}
                    <div className="mt-6 flex w-full max-w-2xl items-center gap-2 rounded-full border border-slate-200 bg-white p-1.5 shadow-[0_8px_24px_rgba(15,23,42,0.04)] focus-within:border-[#FF6B35] focus-within:ring-4 focus-within:ring-orange-100">
                        <input
                            data-testid={TID.askInput}
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            onKeyDown={(e) =>
                                e.key === "Enter" && askAnything()
                            }
                            placeholder="How is my business today?"
                            className="flex-1 bg-transparent px-4 py-2.5 text-[15px] text-slate-900 placeholder:text-slate-400 focus:outline-none"
                        />
                        <button
                            data-testid={TID.askSubmit}
                            onClick={() => askAnything()}
                            className="inline-flex items-center gap-1.5 rounded-full bg-[#FF6B35] px-5 py-2.5 text-sm font-medium text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:-translate-y-0.5 hover:bg-[#E85D2A]"
                        >
                            Ask <ArrowRight size={14} />
                        </button>
                    </div>

                    {/* Suggestion chips */}
                    <div className="mt-4 flex max-w-2xl flex-wrap gap-2">
                        {[
                            "Why are sales down?",
                            "Which branch needs attention?",
                            "What should I do today?",
                            "Forecast next month",
                            "Who are my VIPs?",
                        ].map((s) => (
                            <button
                                key={s}
                                data-testid={`chip-${s.replace(/[^a-z]+/gi, "-").toLowerCase()}`}
                                onClick={() => askAnything(s)}
                                className="rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:border-[#FF6B35] hover:text-[#E85D2A]"
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="flex flex-col items-center gap-3 rounded-3xl border border-slate-200/70 bg-white/80 p-6 backdrop-blur-xl">
                    <HealthRing
                        score={data.health.score}
                        state={data.health.state}
                    />
                    <div
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.2em] ${
                            data.health.state === "green"
                                ? "bg-emerald-50 text-emerald-600"
                                : data.health.state === "yellow"
                                  ? "bg-amber-50 text-amber-600"
                                  : "bg-red-50 text-red-600"
                        }`}
                    >
                        {data.health.state}
                    </div>
                    <div className="grid w-full grid-cols-2 gap-2 text-center text-[11px]">
                        {Object.entries(data.health.components).map(([k, v]) => (
                            <div
                                key={k}
                                className="rounded-md bg-slate-50 px-2 py-1.5"
                            >
                                <div className="text-slate-400">
                                    {k.replace(/_/g, " ")}
                                </div>
                                <div className="font-mono text-sm font-semibold text-slate-900">
                                    {v}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* KPIs — the 8 headline operating metrics */}
            <div className="mt-10 flex items-baseline justify-between">
                <h2 className="font-display text-lg font-semibold tracking-tight text-slate-900">
                    Today&apos;s KPIs
                </h2>
                <button
                    data-testid="home-view-kpis"
                    onClick={() => navigate("/kpis")}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-[#E85D2A] hover:text-[#FF6B35]"
                >
                    View all metrics <ArrowRight size={13} />
                </button>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <KpiTile
                    testId={TID.kpiRevenue}
                    label="Total Revenue"
                    value={t.revenue}
                    change={t.vs_yesterday_pct}
                    money
                    icon={<DollarSign size={16} className="text-slate-300" />}
                    sublabel="vs. yesterday"
                />
                <KpiTile
                    testId={TID.kpiCovers}
                    label="Covers"
                    value={t.covers}
                    change={t.covers_vs_yesterday_pct}
                    icon={<UtensilsCrossed size={16} className="text-slate-300" />}
                    sublabel={`${t.orders} orders today`}
                />
                <KpiTile
                    testId={TID.kpiAov}
                    label="Avg Order Value"
                    value={t.avg_order_value}
                    money
                    icon={<Receipt size={16} className="text-slate-300" />}
                    sublabel="basket size"
                />
                <KpiTile
                    testId={TID.kpiCartAbandon}
                    label="Cart Abandonment"
                    value={t.cart_abandonment_pct}
                    suffix="%"
                    icon={<ShoppingCart size={16} className="text-slate-300" />}
                    sublabel="online checkouts"
                />
                <KpiTile
                    testId={TID.kpiRepeat}
                    label="Repeat Customers"
                    value={data.repeat_rate_pct}
                    suffix="%"
                    icon={<Repeat size={16} className="text-slate-300" />}
                    sublabel="returning guests"
                />
                <KpiTile
                    testId={TID.kpiDiscount}
                    label="Avg Discount"
                    value={t.avg_discount_pct}
                    suffix="%"
                    icon={<Percent size={16} className="text-slate-300" />}
                    sublabel="of subtotal"
                />
                <KpiTile
                    testId={TID.kpiTurnover}
                    label="Table Turnover"
                    value={t.table_turnover}
                    suffix="×"
                    icon={<RotateCw size={16} className="text-slate-300" />}
                    sublabel="turns / table · day"
                    naHint="Needs seating data"
                />
                <KpiTile
                    testId={TID.kpiRevpash}
                    label="RevPASH"
                    value={t.revpash}
                    prefix="$"
                    icon={<Armchair size={16} className="text-slate-300" />}
                    sublabel="revenue / seat · hour"
                    naHint="Needs seating data"
                />
            </div>

            {/* Secondary metrics */}
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <KpiTile
                    testId={TID.kpiOrders}
                    label="Orders"
                    value={t.orders}
                    change={t.orders_vs_yesterday_pct}
                    icon={<ShoppingBag size={16} className="text-slate-300" />}
                    sublabel="today"
                />
                <KpiTile
                    testId={TID.kpiTips}
                    label="Tips"
                    value={t.tips}
                    money
                    icon={<Coins size={16} className="text-slate-300" />}
                    sublabel="customer love"
                />
                <KpiTile
                    testId={TID.kpiCustomers}
                    label="Customers"
                    value={t.customers}
                    icon={<Users size={16} className="text-slate-300" />}
                    sublabel="unique today"
                />
            </div>

            {/* Briefing */}
            <div className="mt-10">
                <Briefing
                    data={data.briefing}
                    onLaunch={onLaunch}
                    onShare={onShare}
                />
            </div>

            {/* Mic hero (floating) */}
            <div className="pointer-events-none fixed bottom-20 left-0 right-0 z-30 flex justify-center lg:bottom-8">
                <div className="pointer-events-auto">
                    <VoiceMic onTranscribed={onTranscribed} />
                </div>
            </div>
        </Layout>
    );
}
