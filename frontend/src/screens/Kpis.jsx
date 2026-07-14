import { useEffect, useState } from "react";
import {
    DollarSign,
    UtensilsCrossed,
    Receipt,
    Percent,
    Repeat,
    ShoppingCart,
    RotateCw,
    Armchair,
    ArrowUpRight,
    ArrowDownRight,
    Minus,
    Gauge,
} from "lucide-react";
import { api, fmtUsd, fmtPct } from "@/lib/api";
import Layout from "@/components/Layout";
import { TID } from "@/constants/testIds";

/* Trend chip — an at-a-glance direction pill next to a value. */
function Trend({ value }) {
    if (typeof value !== "number") return null;
    const up = value > 0;
    const down = value < 0;
    const Icon = up ? ArrowUpRight : down ? ArrowDownRight : Minus;
    return (
        <span
            className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-semibold ${
                up
                    ? "bg-emerald-50 text-emerald-600"
                    : down
                      ? "bg-red-50 text-red-500"
                      : "bg-slate-100 text-slate-400"
            }`}
        >
            <Icon size={12} strokeWidth={2.5} />
            {fmtPct(value, false)}
        </span>
    );
}

/* A single KPI. Null value => "—" plus a plain-language reason it's unavailable
   on the active data source (never a misleading zero). */
function Metric({ label, value, money, unit = "", prefix = "", change, sub, naHint, icon, testId, spread = false }) {
    const nil = value === null || value === undefined || value === "";
    const display = nil ? "—" : money ? fmtUsd(value) : `${prefix}${value}${unit}`;
    return (
        <div
            data-testid={testId}
            className={`fade-up flex flex-col rounded-2xl border border-slate-200/70 bg-white p-5 shadow-[0_2px_8px_rgba(15,23,42,0.04)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(15,23,42,0.07)] ${
                spread ? "justify-between gap-6" : "gap-3"
            }`}
        >
            <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                    {label}
                </span>
                {icon}
            </div>
            <div className="flex items-end gap-2">
                <span
                    className={`font-display text-[32px] font-semibold leading-none tracking-tight tabular-nums ${
                        nil ? "text-slate-300" : "text-slate-900"
                    }`}
                >
                    {display}
                </span>
                {!nil && <Trend value={change} />}
            </div>
            <span className={`text-xs ${nil ? "text-slate-400" : "text-slate-500"}`}>
                {nil ? naHint || "Not tracked on this source" : sub}
            </span>
        </div>
    );
}

/* Signature element: the revenue hero — big mono number + 14-day area sparkline. */
function Sparkline({ data }) {
    if (!data || data.length < 2) return null;
    const W = 520;
    const H = 64;
    const pad = 4;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const x = (i) => pad + (i * (W - 2 * pad)) / (data.length - 1);
    const y = (v) => (max === min ? H / 2 : H - pad - ((v - min) / (max - min)) * (H - 2 * pad));
    const line = data.map((v, i) => `${x(i)},${y(v)}`).join(" ");
    const area = `${pad},${H} ${line} ${W - pad},${H}`;
    return (
        <svg
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
            className="h-16 w-full"
            aria-hidden="true"
        >
            <defs>
                <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FF6B35" stopOpacity="0.28" />
                    <stop offset="100%" stopColor="#FF6B35" stopOpacity="0" />
                </linearGradient>
            </defs>
            <polygon points={area} fill="url(#sparkFill)" />
            <polyline
                points={line}
                fill="none"
                stroke="#FF6B35"
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
            />
        </svg>
    );
}

function RevenueHero({ value, change, series }) {
    return (
        <div
            data-testid={TID.kpiRevenue}
            className="fade-up relative flex flex-col justify-between overflow-hidden rounded-3xl border border-orange-100 bg-gradient-to-br from-white via-white to-orange-50/50 p-6 shadow-[0_2px_18px_rgba(15,23,42,0.05)] sm:col-span-2"
        >
            <div className="absolute -right-12 -top-12 h-40 w-40 rounded-full bg-orange-100/50 blur-3xl" />
            <div className="relative">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.2em] text-[#FF6B35]">
                    <DollarSign size={13} strokeWidth={2.5} />
                    Total Revenue · Today
                </div>
                <div className="mt-2 flex items-end gap-3">
                    <span className="font-display text-6xl font-semibold tracking-tight text-slate-900">
                        {fmtUsd(value)}
                    </span>
                    <span className="mb-1">
                        <Trend value={change} />
                    </span>
                </div>
            </div>
            <div className="relative mt-4">
                <Sparkline data={series} />
                <div className="mt-1 text-[10px] font-medium uppercase tracking-[0.15em] text-slate-400">
                    Last 14 days
                </div>
            </div>
        </div>
    );
}

/* Grouped section — the header encodes the lever the metrics share. */
function Section({ title, note, children }) {
    return (
        <div className="mt-8">
            <div className="flex items-baseline gap-3">
                <h2 className="text-xs font-bold uppercase tracking-[0.22em] text-slate-500">
                    {title}
                </h2>
                <div className="h-px flex-1 bg-slate-200/70" />
                {note && <span className="text-[11px] text-slate-400">{note}</span>}
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
        </div>
    );
}

const ic = (Icon) => <Icon size={16} className="text-slate-300" />;

export default function Kpis() {
    const [data, setData] = useState(null);
    const [series, setSeries] = useState([]);

    useEffect(() => {
        api.get("/dashboard").then((r) => setData(r.data));
        api.get("/revenue?days=14").then((r) =>
            setSeries((r.data.by_day || []).map((d) => d.revenue))
        );
    }, []);

    if (!data)
        return (
            <Layout>
                <div className="flex h-[60vh] items-center justify-center text-slate-400">
                    Loading metrics…
                </div>
            </Layout>
        );

    const t = data.today;
    const live = data.data_source === "square" || data.data_source === "jhapos";

    return (
        <Layout>
            {/* Header */}
            <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                        Performance
                    </div>
                    <h1 className="mt-1 font-display text-4xl font-semibold tracking-tight text-slate-900">
                        Key Metrics
                    </h1>
                    <p className="mt-1 text-[15px] text-slate-500">
                        The eight numbers that run {data.owner?.restaurant || "your restaurant"}.
                    </p>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600">
                    <span
                        className={`h-1.5 w-1.5 rounded-full ${live ? "bg-emerald-500" : "bg-amber-400"}`}
                    />
                    {live ? "Live" : "Demo"} · {data.data_source}
                </span>
            </div>

            {/* Sales pulse — revenue hero + covers + AOV */}
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <RevenueHero value={t.revenue} change={t.vs_yesterday_pct} series={series} />
                <Metric
                    testId={TID.kpiCovers}
                    label="Covers"
                    value={t.covers}
                    change={t.covers_vs_yesterday_pct}
                    sub={`${t.orders} orders today`}
                    icon={ic(UtensilsCrossed)}
                    spread
                />
                <Metric
                    testId={TID.kpiAov}
                    label="Avg Order Value"
                    value={t.avg_order_value}
                    money
                    sub="basket size"
                    icon={ic(Receipt)}
                    spread
                />
            </div>

            {/* Pricing & loyalty */}
            <Section title="Pricing & Loyalty">
                <Metric
                    testId={TID.kpiDiscount}
                    label="Avg Discount"
                    value={t.avg_discount_pct}
                    unit="%"
                    sub="of subtotal given away"
                    icon={ic(Percent)}
                />
                <Metric
                    testId={TID.kpiRepeat}
                    label="Repeat Customers"
                    value={data.repeat_rate_pct}
                    unit="%"
                    sub="returning guests"
                    icon={ic(Repeat)}
                />
                <Metric
                    testId={TID.kpiCartAbandon}
                    label="Cart Abandonment"
                    value={t.cart_abandonment_pct}
                    unit="%"
                    sub="online checkouts left behind"
                    naHint="No checkout funnel on this source"
                    icon={ic(ShoppingCart)}
                />
            </Section>

            {/* Seating efficiency */}
            <Section title="Seating Efficiency" note="dine-in only">
                <Metric
                    testId={TID.kpiTurnover}
                    label="Table Turnover"
                    value={t.table_turnover}
                    unit="×"
                    sub="turns / table · day"
                    naHint="Needs seat capacity"
                    icon={ic(RotateCw)}
                />
                <Metric
                    testId={TID.kpiRevpash}
                    label="RevPASH"
                    value={t.revpash}
                    prefix="$"
                    sub="revenue / seat · hour"
                    naHint="Needs seat capacity"
                    icon={ic(Armchair)}
                />
            </Section>

            {/* Legend for unavailable metrics */}
            <div className="mt-8 flex items-center gap-2 text-xs text-slate-400">
                <Gauge size={14} />
                A dash (—) means the metric isn&apos;t measurable on the connected
                data source — never an estimated or zero value.
            </div>
        </Layout>
    );
}
