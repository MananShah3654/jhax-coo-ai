import { useState } from "react";
import { api } from "@/lib/api";
import Layout from "@/components/Layout";
import { Sparkles, Loader2, Send } from "lucide-react";
import { TID } from "@/constants/testIds";
import { toast } from "sonner";

const AUDIENCES = [
    { id: "vip", label: "VIP customers" },
    { id: "at_risk", label: "At-risk (inactive 30+ days)" },
    { id: "new", label: "New customers (first visit)" },
    { id: "all", label: "All customers" },
];
const CHANNELS = [
    { id: "sms", label: "SMS" },
    { id: "email", label: "Email" },
    { id: "push", label: "Push" },
    { id: "loyalty", label: "Loyalty" },
];
const GOALS = [
    "Reactivate inactive customers",
    "Drive lunch traffic",
    "Promote weekend brunch",
    "Increase repeat visits",
    "Push the new BBQ Ribs platter",
];

export default function Marketing() {
    const [audience, setAudience] = useState("at_risk");
    const [channel, setChannel] = useState("sms");
    const [goal, setGoal] = useState(GOALS[0]);
    const [draft, setDraft] = useState(null);
    const [busy, setBusy] = useState(false);

    const generate = async () => {
        setBusy(true);
        setDraft(null);
        try {
            const { data } = await api.post("/campaigns/generate", {
                audience: AUDIENCES.find((a) => a.id === audience).label,
                channel,
                goal,
            });
            setDraft(data.draft);
        } catch {
            toast.error("Campaign generation failed");
        } finally {
            setBusy(false);
        }
    };

    const launch = async () => {
        try {
            await api.post("/actions/execute", {
                id: "campaign_launch",
                kind: "campaign",
                label: draft?.subject || "Campaign",
                payload: { audience, channel, draft },
            });
            toast.success("Campaign scheduled for delivery");
        } catch {
            toast.error("Launch failed");
        }
    };

    return (
        <Layout>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Marketing AI
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                Generate a campaign in seconds
            </h1>

            <div className="mt-6 grid items-start gap-6 lg:grid-cols-[1fr_1fr]">
                <div className="rounded-3xl border border-slate-200 bg-white p-6">
                    <div className="space-y-5">
                        <div>
                            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                Audience
                            </label>
                            <select
                                data-testid={TID.campAudience}
                                value={audience}
                                onChange={(e) => setAudience(e.target.value)}
                                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                            >
                                {AUDIENCES.map((a) => (
                                    <option key={a.id} value={a.id}>
                                        {a.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                Channel
                            </label>
                            <div className="mt-1.5 flex flex-wrap gap-2">
                                {CHANNELS.map((c) => (
                                    <button
                                        key={c.id}
                                        data-testid={`${TID.campChannel}-${c.id}`}
                                        onClick={() => setChannel(c.id)}
                                        className={`rounded-full border px-4 py-2 text-sm font-medium transition-all ${
                                            channel === c.id
                                                ? "border-[#FF6B35] bg-orange-50 text-[#E85D2A]"
                                                : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                                        }`}
                                    >
                                        {c.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div>
                            <label className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                Goal
                            </label>
                            <input
                                data-testid={TID.campGoal}
                                value={goal}
                                onChange={(e) => setGoal(e.target.value)}
                                list="goals-list"
                                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm focus:border-[#FF6B35] focus:outline-none focus:ring-4 focus:ring-orange-100"
                            />
                            <datalist id="goals-list">
                                {GOALS.map((g) => (
                                    <option key={g} value={g} />
                                ))}
                            </datalist>
                        </div>
                        <button
                            data-testid={TID.campGenerate}
                            onClick={generate}
                            disabled={busy}
                            className="inline-flex items-center gap-2 rounded-full bg-[#FF6B35] px-6 py-2.5 text-sm font-medium text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:bg-[#E85D2A] disabled:opacity-50"
                        >
                            {busy ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <Sparkles size={14} />
                            )}
                            {busy ? "Generating…" : "Generate Campaign"}
                        </button>
                    </div>
                </div>

                <div
                    data-testid={TID.campResult}
                    className="rounded-3xl border border-slate-200 bg-white p-6"
                >
                    {!draft && !busy && (
                        <div className="grid h-full place-items-center text-center text-sm text-slate-400">
                            Generated copy will appear here.
                        </div>
                    )}
                    {busy && (
                        <div className="grid h-full place-items-center text-sm text-slate-400">
                            <div className="flex items-center gap-2">
                                <Loader2
                                    size={14}
                                    className="animate-spin text-[#FF6B35]"
                                />
                                Drafting copy…
                            </div>
                        </div>
                    )}
                    {draft && (
                        <div className="space-y-4">
                            <div>
                                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                                    Subject
                                </div>
                                <div className="mt-0.5 font-display text-xl font-semibold text-slate-900">
                                    {draft.subject}
                                </div>
                            </div>
                            <div>
                                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                                    Body
                                </div>
                                <p className="mt-0.5 whitespace-pre-line text-[15px] leading-relaxed text-slate-700">
                                    {draft.body}
                                </p>
                            </div>
                            <div className="flex flex-wrap gap-3">
                                <div className="rounded-xl bg-slate-50 px-3 py-2">
                                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                        CTA
                                    </div>
                                    <div className="font-display text-base font-semibold text-slate-900">
                                        {draft.cta}
                                    </div>
                                </div>
                                <div className="rounded-xl bg-slate-50 px-3 py-2">
                                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                        Est. Reach
                                    </div>
                                    <div className="font-display text-base font-semibold text-slate-900">
                                        {draft.estimated_reach?.toLocaleString() || "—"}
                                    </div>
                                </div>
                                <div className="rounded-xl bg-emerald-50 px-3 py-2">
                                    <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-emerald-700">
                                        Est. Revenue
                                    </div>
                                    <div className="font-display text-base font-semibold text-emerald-600">
                                        $
                                        {draft.estimated_revenue?.toLocaleString() ||
                                            "—"}
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={launch}
                                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
                            >
                                <Send size={14} /> Launch Campaign
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </Layout>
    );
}
