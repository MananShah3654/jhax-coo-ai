import { useEffect, useState } from "react";
import { api, fmtUsd } from "@/lib/api";
import Layout from "@/components/Layout";

export default function Forecast() {
    const [data, setData] = useState(null);
    useEffect(() => {
        api.get("/forecast?days=30").then((r) => setData(r.data));
    }, []);
    if (!data)
        return (
            <Layout>
                <div className="text-slate-400">Loading forecast…</div>
            </Layout>
        );

    const maxVal = Math.max(...data.series.map((s) => s.projected_revenue));
    return (
        <Layout>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                AI Forecasting · next 30 days
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                Your revenue runway
            </h1>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                        Projected Revenue
                    </div>
                    <div className="mt-1 font-display text-3xl font-semibold text-slate-900">
                        {fmtUsd(data.projected_revenue)}
                    </div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-white p-5">
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                        Daily Average
                    </div>
                    <div className="mt-1 font-display text-3xl font-semibold text-slate-900">
                        {fmtUsd(data.daily_avg)}
                    </div>
                </div>
                <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-5">
                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700">
                        Confidence
                    </div>
                    <div className="mt-1 font-display text-3xl font-semibold text-emerald-600">
                        {data.confidence}%
                    </div>
                </div>
            </div>

            <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-5">
                <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                    30-day projection
                </div>
                <div className="mt-4 grid grid-cols-15 items-end gap-1.5">
                    {data.series.map((s) => (
                        <div
                            key={s.date}
                            className="group relative flex flex-col items-center"
                        >
                            <div
                                className="w-full rounded-t-md bg-gradient-to-t from-[#FF6B35] to-[#FFA168] transition-all hover:from-[#E85D2A]"
                                style={{
                                    height: `${(s.projected_revenue / maxVal) * 140}px`,
                                    minHeight: 4,
                                }}
                                title={`${s.date}: ${fmtUsd(s.projected_revenue)}`}
                            />
                            <div className="absolute -top-7 hidden whitespace-nowrap rounded bg-slate-900 px-2 py-1 text-[10px] font-medium text-white group-hover:block">
                                {fmtUsd(s.projected_revenue)}
                            </div>
                        </div>
                    ))}
                </div>
                <div className="mt-2 flex justify-between text-[10px] font-medium text-slate-400">
                    <span>{data.series[0].date}</span>
                    <span>{data.series[data.series.length - 1].date}</span>
                </div>
            </div>
        </Layout>
    );
}
