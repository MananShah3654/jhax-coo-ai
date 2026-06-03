import { useEffect, useState } from "react";
import { api, fmtUsd } from "@/lib/api";
import Layout from "@/components/Layout";
import { TrendingUp, TrendingDown } from "lucide-react";

function MenuRow({ item }) {
    return (
        <tr className="border-t border-slate-100 hover:bg-slate-50/40">
            <td className="px-5 py-3.5">
                <div className="font-medium text-slate-900">{item.name}</div>
                <div className="text-xs text-slate-500">{item.category}</div>
            </td>
            <td className="px-5 py-3.5 text-right text-slate-700">
                {item.units_sold}
            </td>
            <td className="px-5 py-3.5 text-right font-mono text-slate-900">
                {fmtUsd(item.revenue)}
            </td>
            <td className="px-5 py-3.5 text-right font-mono text-emerald-600">
                {fmtUsd(item.profit)}
            </td>
            <td className="px-5 py-3.5 text-right text-slate-700">
                {item.margin_pct}%
            </td>
        </tr>
    );
}

export default function Menu() {
    const [data, setData] = useState(null);
    useEffect(() => {
        api.get("/menu?days=30").then((r) => setData(r.data));
    }, []);
    if (!data)
        return (
            <Layout>
                <div className="text-slate-400">Loading menu…</div>
            </Layout>
        );

    return (
        <Layout>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Menu Intelligence · last 30 days
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                What's selling, what's not
            </h1>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
                <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                    <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3.5 text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700">
                        <TrendingUp size={12} /> Most Profitable
                    </div>
                    <table className="w-full text-sm">
                        <thead className="text-left text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                            <tr>
                                <th className="px-5 py-2">Item</th>
                                <th className="px-5 py-2 text-right">Units</th>
                                <th className="px-5 py-2 text-right">Rev</th>
                                <th className="px-5 py-2 text-right">Profit</th>
                                <th className="px-5 py-2 text-right">Margin</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.top.map((m) => (
                                <MenuRow key={m.id} item={m} />
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
                    <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3.5 text-[10px] font-bold uppercase tracking-[0.18em] text-red-500">
                        <TrendingDown size={12} /> Underperforming
                    </div>
                    <table className="w-full text-sm">
                        <thead className="text-left text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                            <tr>
                                <th className="px-5 py-2">Item</th>
                                <th className="px-5 py-2 text-right">Units</th>
                                <th className="px-5 py-2 text-right">Rev</th>
                                <th className="px-5 py-2 text-right">Profit</th>
                                <th className="px-5 py-2 text-right">Margin</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.bottom.map((m) => (
                                <MenuRow key={m.id} item={m} />
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </Layout>
    );
}
