import { useEffect, useState } from "react";
import {
    TrendingUp,
    TrendingDown,
    Clock,
    Info,
    AlertTriangle,
    Megaphone,
} from "lucide-react";
import { api, fmtUsd } from "@/lib/api";
import Layout from "@/components/Layout";
import { TID } from "@/constants/testIds";

function Delta({ pct }) {
    // null => no baseline to compare against. "+100%" off a zero base is noise.
    if (pct === null || pct === undefined) {
        return <span className="text-xs text-slate-400">no baseline</span>;
    }
    const up = pct > 0;
    return (
        <span
            className={`inline-flex items-center gap-1 text-xs font-semibold ${
                up ? "text-emerald-600" : pct < 0 ? "text-red-500" : "text-slate-400"
            }`}
        >
            {up ? <TrendingUp size={12} /> : pct < 0 ? <TrendingDown size={12} /> : null}
            {up ? "+" : ""}
            {pct}%
        </span>
    );
}

function RoiCell({ roi }) {
    if (roi.status === "still_measuring") {
        return (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <Clock size={12} className="text-slate-400" />
                Still measuring — {roi.days_remaining} day
                {roi.days_remaining === 1 ? "" : "s"} left
            </div>
        );
    }
    if (roi.status === "no_segment") {
        return <div className="text-xs text-slate-400">{roi.note}</div>;
    }
    return (
        <div className="space-y-1">
            <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold text-slate-900">
                    {fmtUsd(roi.after.revenue)}
                </span>
                <Delta pct={roi.revenue_delta_pct} />
            </div>
            <div className="text-[11px] text-slate-500">
                vs {fmtUsd(roi.before.revenue)} before · {roi.after.orders} orders
                (was {roi.before.orders})
            </div>
        </div>
    );
}

export default function CampaignRoi() {
    const [data, setData] = useState(null);
    const [err, setErr] = useState(null);

    useEffect(() => {
        api.get("/campaigns/roi")
            .then((r) => setData(r.data))
            .catch((e) =>
                setErr(e?.response?.data?.detail || "Couldn't load campaigns"),
            );
    }, []);

    if (err) {
        return (
            <Layout>
                <div className="py-24 text-center text-sm text-red-500">{err}</div>
            </Layout>
        );
    }
    if (!data) {
        return (
            <Layout>
                <div className="py-24 text-center text-sm text-slate-400">
                    Loading campaigns…
                </div>
            </Layout>
        );
    }

    const campaigns = data.campaigns || [];

    return (
        <Layout>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Marketing · Campaign ROI
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                Did the campaign move revenue?
            </h1>

            {/* Synthetic-date warning outranks everything else on this screen:
                without it the numbers below look earned. */}
            {data.synthetic_dates && (
                <div
                    data-testid={TID.roiSyntheticWarning}
                    className="mt-4 flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800"
                >
                    <AlertTriangle size={14} className="mt-px shrink-0" />
                    <span>
                        <b>These dates are synthetic.</b> The <b>{data.data_source}</b>{" "}
                        source is running with demo date-spreading
                        (SQUARE_DEMO_SPREAD_DAYS), which fabricates every order
                        timestamp because Square can’t backdate orders. Any
                        before/after window here is arithmetic over invented history —
                        treat these figures as a UI demonstration, not a result. Set
                        SQUARE_DEMO_SPREAD_DAYS=0 for real dates.
                    </span>
                </div>
            )}

            <div className="mt-3 flex items-start gap-2 rounded-2xl border border-slate-200/70 bg-slate-50/60 p-4 text-xs text-slate-500">
                <Info size={14} className="mt-px shrink-0 text-slate-400" />
                <span>{data.disclaimer}</span>
            </div>

            {campaigns.length === 0 ? (
                <div
                    data-testid={TID.roiEmpty}
                    className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white/60 py-16 text-center"
                >
                    <Megaphone size={22} className="mx-auto text-slate-300" />
                    <p className="mt-3 text-sm font-medium text-slate-600">
                        No campaigns sent yet.
                    </p>
                    <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-400">
                        This lists real broadcasts only — a campaign appears here once
                        it has actually been sent from Marketing AI. Nothing is
                        simulated.
                    </p>
                </div>
            ) : (
                <div className="mt-6 overflow-hidden rounded-3xl border border-slate-200 bg-white">
                    <div className="overflow-x-auto">
                        <table
                            data-testid={TID.roiTable}
                            className="w-full min-w-[720px] text-sm"
                        >
                            <thead className="border-b border-slate-100 text-left text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                <tr>
                                    <th className="px-5 py-3">Audience</th>
                                    <th className="px-5 py-3">Channel</th>
                                    <th className="px-5 py-3">Sent</th>
                                    <th className="px-5 py-3 text-right">Recipients</th>
                                    <th className="px-5 py-3">Result</th>
                                    <th className="px-5 py-3">7d after vs 7d before</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                                {campaigns.map((c) => (
                                    <tr key={c.id} className="hover:bg-slate-50/60">
                                        <td className="px-5 py-4 font-medium text-slate-800">
                                            {c.audience}
                                        </td>
                                        <td className="px-5 py-4 text-slate-600">
                                            {c.channel}
                                        </td>
                                        <td className="px-5 py-4 text-slate-600">
                                            {c.sent_at
                                                ? new Date(c.sent_at).toLocaleDateString()
                                                : "—"}
                                        </td>
                                        <td className="px-5 py-4 text-right font-mono text-slate-800">
                                            {c.recipient_count}
                                        </td>
                                        <td className="px-5 py-4">
                                            <span
                                                className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                                                    c.status === "sent"
                                                        ? "bg-emerald-50 text-emerald-600"
                                                        : c.status === "partial"
                                                          ? "bg-amber-50 text-amber-600"
                                                          : "bg-red-50 text-red-500"
                                                }`}
                                            >
                                                {c.status}
                                            </span>
                                            <div className="mt-1 text-[10px] text-slate-400">
                                                {c.sent_count} sent · {c.failed_count}{" "}
                                                failed
                                            </div>
                                        </td>
                                        <td className="px-5 py-4">
                                            <RoiCell roi={c.roi} />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </Layout>
    );
}
