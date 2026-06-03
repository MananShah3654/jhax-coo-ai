import { useEffect, useState } from "react";
import { api, fmtUsd, fmtPct } from "@/lib/api";
import Layout from "@/components/Layout";
import { Crown, AlertTriangle } from "lucide-react";
import { TID } from "@/constants/testIds";

export default function Branches() {
    const [data, setData] = useState(null);
    useEffect(() => {
        api.get("/branches?days=7").then((r) => setData(r.data));
    }, []);
    if (!data)
        return (
            <Layout>
                <div className="text-slate-400">Loading branches…</div>
            </Layout>
        );

    const best = data.branches[0];
    const worst = data.branches[data.branches.length - 1];

    return (
        <Layout>
            <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Multi-Location · last 7 days
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                Branch Performance
            </h1>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-5">
                    <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-emerald-700">
                        <Crown size={12} /> Best Branch
                    </div>
                    <div className="mt-1 font-display text-2xl font-semibold text-slate-900">
                        {best.name}
                    </div>
                    <div className="text-sm text-slate-600">
                        {fmtUsd(best.revenue)} · {best.orders} orders · {" "}
                        <span className="font-semibold text-emerald-600">
                            {fmtPct(best.growth_pct)}
                        </span>
                    </div>
                </div>
                <div className="rounded-2xl border border-red-100 bg-red-50/60 p-5">
                    <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.25em] text-red-700">
                        <AlertTriangle size={12} /> Needs Attention
                    </div>
                    <div className="mt-1 font-display text-2xl font-semibold text-slate-900">
                        {worst.name}
                    </div>
                    <div className="text-sm text-slate-600">
                        {fmtUsd(worst.revenue)} · {worst.orders} orders · {" "}
                        <span className="font-semibold text-red-500">
                            {fmtPct(worst.growth_pct)}
                        </span>
                    </div>
                </div>
            </div>

            <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-left text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
                        <tr>
                            <th className="px-5 py-3">Branch</th>
                            <th className="px-5 py-3">Manager</th>
                            <th className="px-5 py-3 text-right">Revenue</th>
                            <th className="px-5 py-3 text-right">Orders</th>
                            <th className="px-5 py-3 text-right">AOV</th>
                            <th className="px-5 py-3 text-right">Growth</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.branches.map((b) => (
                            <tr
                                key={b.id}
                                data-testid={TID.branchRow(b.id)}
                                className="border-t border-slate-100 hover:bg-slate-50/50"
                            >
                                <td className="px-5 py-4">
                                    <div className="font-display text-base font-semibold text-slate-900">
                                        {b.name}
                                    </div>
                                    <div className="text-xs text-slate-500">
                                        {b.city}
                                    </div>
                                </td>
                                <td className="px-5 py-4 text-slate-700">
                                    {b.manager}
                                </td>
                                <td className="px-5 py-4 text-right font-mono font-semibold text-slate-900">
                                    {fmtUsd(b.revenue)}
                                </td>
                                <td className="px-5 py-4 text-right text-slate-700">
                                    {b.orders}
                                </td>
                                <td className="px-5 py-4 text-right text-slate-700">
                                    {fmtUsd(b.avg_order_value)}
                                </td>
                                <td
                                    className={`px-5 py-4 text-right font-semibold ${b.growth_pct >= 0 ? "text-emerald-600" : "text-red-500"}`}
                                >
                                    {fmtPct(b.growth_pct)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </Layout>
    );
}
