import { useEffect, useState } from "react";
import {
    DollarSign,
    UtensilsCrossed,
    Receipt,
    ShoppingCart,
    Repeat,
    Percent,
    RotateCw,
    Armchair,
    Info,
} from "lucide-react";
import { api } from "@/lib/api";
import Layout from "@/components/Layout";
import KpiTile from "@/components/KpiTile";
import Sparkline from "@/components/Sparkline";
import { TID } from "@/constants/testIds";

function Section({ title, blurb, children }) {
    return (
        <section className="mt-9 first:mt-0">
            <div className="flex items-baseline justify-between">
                <h2 className="font-display text-lg font-semibold tracking-tight text-slate-900">
                    {title}
                </h2>
                <span className="text-xs text-slate-400">{blurb}</span>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</div>
        </section>
    );
}

export default function Kpis() {
    const [data, setData] = useState(null);

    useEffect(() => {
        api.get("/dashboard").then((r) => setData(r.data));
    }, []);

    if (!data) {
        return (
            <Layout>
                <div className="py-24 text-center text-sm text-slate-400">
                    Loading metrics…
                </div>
            </Layout>
        );
    }

    const t = data.today || {};
    const trend = (data.revenue_14d || []).map((d) => d.revenue);
    // Any KPI the active source can't measure arrives as null and renders "—"
    // via KpiTile, never a fabricated 0.
    const unavailable = [
        ["Cart Abandonment", t.cart_abandonment_pct],
        ["Table Turnover", t.table_turnover],
        ["RevPASH", t.revpash],
    ].filter(([, v]) => v === null || v === undefined);

    return (
        <Layout>
            <div className="flex items-baseline justify-between">
                <div>
                    <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                        Key Metrics
                    </h1>
                    <p className="mt-1 text-sm text-slate-500">
                        The eight headline operating KPIs, live from{" "}
                        <span className="font-semibold text-slate-700">
                            {data.data_source}
                        </span>
                        .
                    </p>
                </div>
            </div>

            {unavailable.length > 0 && (
                <div className="mt-5 flex items-start gap-2 rounded-2xl border border-slate-200/70 bg-slate-50/60 p-4 text-xs text-slate-500">
                    <Info size={14} className="mt-px shrink-0 text-slate-400" />
                    <span>
                        {unavailable.map(([n]) => n).join(", ")}{" "}
                        {unavailable.length === 1 ? "is" : "are"} shown as “—”: the{" "}
                        <b>{data.data_source}</b> source doesn’t expose the underlying
                        data. We show nothing rather than a misleading zero.
                    </span>
                </div>
            )}

            <Section title="Sales pulse" blurb="today vs. yesterday">
                <KpiTile
                    testId={TID.kpiRevenue}
                    label="Total Revenue"
                    value={t.revenue}
                    change={t.vs_yesterday_pct}
                    money
                    icon={<DollarSign size={16} className="text-slate-300" />}
                    sublabel="vs. yesterday · 14-day trend"
                    chart={<Sparkline points={trend} />}
                />
                <KpiTile
                    testId={TID.kpiCovers}
                    label="Covers"
                    value={t.covers}
                    change={t.covers_vs_yesterday_pct}
                    icon={<UtensilsCrossed size={16} className="text-slate-300" />}
                    sublabel={`${t.orders ?? 0} orders today`}
                />
                <KpiTile
                    testId={TID.kpiAov}
                    label="Avg Order Value"
                    value={t.avg_order_value}
                    change={t.aov_vs_yesterday_pct}
                    money
                    icon={<Receipt size={16} className="text-slate-300" />}
                    sublabel="basket size"
                />
            </Section>

            <Section title="Pricing & Loyalty" blurb="discounting and repeat behaviour">
                <KpiTile
                    testId={TID.kpiDiscount}
                    label="Avg Discount"
                    value={t.avg_discount_pct}
                    suffix="%"
                    icon={<Percent size={16} className="text-slate-300" />}
                    sublabel="of subtotal"
                    naHint="No discount data on this source"
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
                    testId={TID.kpiCartAbandon}
                    label="Cart Abandonment"
                    value={t.cart_abandonment_pct}
                    suffix="%"
                    icon={<ShoppingCart size={16} className="text-slate-300" />}
                    sublabel="online checkouts"
                    naHint="Needs checkout-session data"
                />
            </Section>

            <Section title="Seating Efficiency" blurb="dine-in capacity yield">
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
            </Section>
        </Layout>
    );
}
