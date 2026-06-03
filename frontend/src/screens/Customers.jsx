import { useEffect, useState } from "react";
import { api, fmtUsd } from "@/lib/api";
import Layout from "@/components/Layout";
import { Star, AlertTriangle, Sparkles } from "lucide-react";

function StatCard({ label, value, accent }) {
    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                {label}
            </div>
            <div
                className={`mt-1 font-display text-3xl font-semibold ${accent || "text-slate-900"}`}
            >
                {value}
            </div>
        </div>
    );
}

function CustomerList({ list, badge, badgeCls, Icon }) {
    return (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
            <div
                className={`mb-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${badgeCls}`}
            >
                <Icon size={11} /> {badge}
            </div>
            <ul className="divide-y divide-slate-100">
                {list.map((c) => (
                    <li
                        key={c.id}
                        className="flex items-center justify-between py-3"
                    >
                        <div>
                            <div className="font-medium text-slate-900">
                                {c.name}
                            </div>
                            <div className="text-xs text-slate-500">
                                {c.visits} visits · last visit{" "}
                                {c.last_visit_days_ago}d ago
                            </div>
                        </div>
                        <div className="text-right">
                            <div className="font-mono font-semibold text-slate-900">
                                {fmtUsd(c.lifetime_value)}
                            </div>
                            <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400">
                                LTV
                            </div>
                        </div>
                    </li>
                ))}
            </ul>
        </div>
    );
}

export default function Customers() {
    const [data, setData] = useState(null);
    useEffect(() => {
        api.get("/customers").then((r) => setData(r.data));
    }, []);
    if (!data)
        return (
            <Layout>
                <div className="text-slate-400">Loading…</div>
            </Layout>
        );

    return (
        <Layout>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Customer Intelligence
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                Who's eating with you
            </h1>

            <div className="mt-6 grid gap-4 md:grid-cols-4">
                <StatCard label="Total" value={data.total_customers} />
                <StatCard
                    label="VIP"
                    value={data.vip_count}
                    accent="text-emerald-600"
                />
                <StatCard
                    label="At Risk"
                    value={data.at_risk_count}
                    accent="text-red-500"
                />
                <StatCard
                    label="Repeat Rate"
                    value={`${data.repeat_rate_pct}%`}
                />
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
                <CustomerList
                    list={data.top_vips}
                    badge="Top VIPs"
                    badgeCls="bg-emerald-50 text-emerald-600"
                    Icon={Star}
                />
                <CustomerList
                    list={data.at_risk_list}
                    badge="At-Risk Customers"
                    badgeCls="bg-red-50 text-red-500"
                    Icon={AlertTriangle}
                />
            </div>

            <div className="mt-6 rounded-2xl border border-orange-100 bg-orange-50/60 p-5">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                    <Sparkles size={12} /> Opportunity
                </div>
                <p className="mt-1 text-sm text-slate-700">
                    Avg lifetime value is{" "}
                    <b>{fmtUsd(data.avg_lifetime_value)}</b>. Reactivating just
                    20% of your at-risk segment could unlock{" "}
                    <b className="text-emerald-600">
                        {fmtUsd(
                            data.at_risk_count *
                                data.avg_lifetime_value *
                                0.2
                        )}
                    </b>{" "}
                    in recovered revenue.
                </p>
            </div>
        </Layout>
    );
}
