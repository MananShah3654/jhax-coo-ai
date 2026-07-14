import { useState } from "react";
import {
    Megaphone, Share2, ArrowUpRight, Bell, Sparkles, FileText,
    Volume2, Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { TID } from "@/constants/testIds";
import { openShareModal } from "@/components/ShareModal";

const KIND_META = {
    campaign:  { Icon: Megaphone,    cls: "bg-[#FF6B35] text-white hover:bg-[#e85d2a]" },
    share:     { Icon: Share2,       cls: "bg-slate-900 text-white hover:bg-slate-800" },
    navigate:  { Icon: ArrowUpRight, cls: "bg-slate-100 text-slate-900 hover:bg-slate-200" },
    notify:    { Icon: Bell,         cls: "bg-amber-500 text-white hover:bg-amber-600" },
    promotion: { Icon: Sparkles,     cls: "bg-[#FF6B35] text-white hover:bg-[#e85d2a]" },
    report:    { Icon: FileText,     cls: "bg-slate-900 text-white hover:bg-slate-800" },
};

const SHARE_TYPES = new Set([
    "daily", "weekly", "monthly", "branch", "investor", "marketing",
]);

function ActionButton({ act, idx, msgIdx }) {
    const navigate = useNavigate();
    const [busy, setBusy] = useState(false);
    const meta = KIND_META[act.kind] || KIND_META.navigate;
    const { Icon } = meta;

    const onClick = async () => {
        if (act.kind === "navigate") {
            navigate(act.target || "/home");
            return;
        }
        if (act.kind === "campaign") {
            try {
                sessionStorage.setItem(
                    "campaign_prefill",
                    JSON.stringify(act.prefill || {})
                );
            } catch {}
            navigate("/marketing", { state: { prefill: act.prefill || {} } });
            return;
        }
        if (act.kind === "promotion") {
            try {
                sessionStorage.setItem(
                    "promotion_prefill",
                    JSON.stringify(act.prefill || {})
                );
            } catch {}
            navigate("/promotions", { state: { prefill: act.prefill || {} } });
            return;
        }
        if (act.kind === "notify") {
            try {
                sessionStorage.setItem(
                    "manager_prefill",
                    JSON.stringify({
                        label: act.label,
                        message: act.prefill?.message || act.label,
                        branch: act.prefill?.branch,
                    })
                );
            } catch {}
            navigate("/manager", { state: { prefill: act.prefill || {} } });
            return;
        }
        if (act.kind === "share" || act.kind === "report") {
            const t = SHARE_TYPES.has(act.target) ? act.target : "daily";
            openShareModal(t);
            return;
        }
        setBusy(true);
        try {
            const { data } = await api.post("/actions/execute", act);
            toast.success(data.detail || "Action executed");
        } catch {
            toast.error("Action failed");
        } finally {
            setBusy(false);
        }
    };

    return (
        <button
            data-testid={TID.chatActionBtn(msgIdx ?? 0, act.id || idx)}
            onClick={onClick}
            disabled={busy}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${meta.cls} disabled:translate-y-0 disabled:opacity-60`}
        >
            {busy ? (
                <Loader2 size={14} className="animate-spin" />
            ) : (
                <Icon size={14} />
            )}
            <span>{act.label}</span>
        </button>
    );
}

/**
 * Compact Decision Card — designed for at-a-glance scanning.
 * - Status is the hero (big).
 * - Reason + Opportunity collapse into a single tight paragraph.
 * - Action is implied by the button; we don't repeat it in text.
 * - Expected impact shows as a green pill.
 */
export default function DecisionCard({
    reply,
    streaming = false,
    msgIdx,
    onPlayVoice,
    voicePlaying = false,
    onSuggestion,
}) {
    if (!reply) return null;

    // Clarification mode
    if (reply.clarify) {
        return (
            <div className="decision-card card-sheen fade-up relative w-full max-w-2xl overflow-hidden rounded-[30px] rounded-tl-lg border border-white/60 bg-gradient-to-b from-orange-50/50 via-white to-white p-7 ring-1 ring-orange-100/60">
                <span className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-[#FF6B35] via-[#F7931E] to-[#FF6B35]" />
                <div className="mb-4 flex items-center gap-2.5">
                    <div className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-[#FF6B35] to-[#E85D2A] text-white shadow-[0_6px_16px_rgba(255,107,53,0.4)]">
                        <Sparkles size={14} />
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-[0.24em] text-gradient-warm">
                        AI COO · needs a bit more
                    </span>
                </div>
                <p className="font-display text-[27px] font-semibold leading-[1.2] tracking-tight text-slate-900">
                    {reply.clarify}
                    {streaming && <span className="caret" />}
                </p>
                {Array.isArray(reply.suggestions) && reply.suggestions.length > 0 && (
                    <div className="mt-5 flex flex-wrap gap-2">
                        {reply.suggestions.map((s, i) => (
                            <button
                                key={i}
                                data-testid={`clarify-suggestion-${i}`}
                                onClick={() => onSuggestion?.(s)}
                                className="rounded-full border border-slate-200 bg-white/80 px-4 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition-all hover:-translate-y-0.5 hover:border-[#FF6B35] hover:text-[#E85D2A] hover:shadow-md"
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    const { status, reason, opportunity, expected_impact, metrics = [], actions = [] } =
        reply;

    return (
        <div
            className={`decision-card fade-up relative w-full overflow-hidden rounded-[30px] rounded-tl-lg border border-orange-100 bg-gradient-to-b from-orange-50/60 via-white to-white p-7 ring-1 ring-orange-100/70 sm:p-8 ${
                streaming ? "" : "card-sheen"
            }`}
        >
            {/* Warm accent bar — even, branded framing with no directional glow */}
            <span className="pointer-events-none absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-[#FF6B35] via-[#F7931E] to-[#FF6B35]" />

            <div className="relative">
                {/* AI COO persona */}
                <div className="mb-4 flex items-center gap-2.5">
                    <div className="relative grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-[#FF6B35] to-[#E85D2A] text-white shadow-[0_6px_16px_rgba(255,107,53,0.4)]">
                        <Sparkles size={14} />
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-[0.24em] text-gradient-warm">
                        AI COO
                    </span>
                    <span className="flex items-center gap-1.5 rounded-full bg-orange-50 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#E85D2A] ring-1 ring-orange-100">
                        <span className="live-dot h-1.5 w-1.5 rounded-full bg-[#FF6B35]" />
                        {streaming ? "Thinking" : "Decision"}
                    </span>
                </div>

                {/* Hero status + impact pill + voice button */}
                <div className="flex items-start justify-between gap-3">
                    <h3 className="font-display text-[31px] font-semibold leading-[1.1] tracking-tight text-slate-900 sm:text-[34px]">
                        {status}
                        {streaming && <span className="caret" />}
                    </h3>
                    <div className="flex shrink-0 items-center gap-2">
                        {expected_impact && (
                            <span className="rounded-full bg-gradient-to-b from-emerald-50 to-emerald-100/60 px-3 py-1 font-mono text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">
                                {expected_impact}
                            </span>
                        )}
                        {onPlayVoice && (
                            <button
                                data-testid={TID.chatPlay(msgIdx ?? 0)}
                                onClick={onPlayVoice}
                                className="grid h-8 w-8 place-items-center rounded-full bg-orange-50 text-[#E85D2A] ring-1 ring-orange-100 transition-colors hover:bg-[#FF6B35] hover:text-white"
                                title="Read aloud"
                            >
                                {voicePlaying ? (
                                    <Loader2 size={12} className="animate-spin" />
                                ) : (
                                    <Volume2 size={12} />
                                )}
                            </button>
                        )}
                    </div>
                </div>

                {/* Tight rationale (reason + opportunity merged) */}
                {(reason || opportunity) && (
                    <p className="mt-5 border-l-[3px] border-transparent pl-4 text-[15.5px] leading-[1.72] text-slate-600 [border-image:linear-gradient(180deg,#FF6B35,#F7931E)_1] [text-wrap:pretty]">
                        {reason}
                        {reason && opportunity && (
                            <span className="text-orange-300"> &nbsp;·&nbsp; </span>
                        )}
                        {opportunity && (
                            <span className="font-medium text-slate-800">{opportunity}</span>
                        )}
                    </p>
                )}

                {/* Metrics — compact stat tiles (label over value) with a warm accent */}
                {metrics.length > 0 && (
                    <div className="mt-6 flex flex-wrap gap-3">
                        {metrics.map((m, i) => (
                            <div
                                key={i}
                                className="rounded-2xl border border-l-[3px] border-slate-200/80 border-l-[#FF6B35] bg-gradient-to-b from-white to-orange-50/40 px-4 py-2.5 shadow-[0_1px_3px_rgba(15,23,42,0.05)] transition-all hover:-translate-y-0.5 hover:border-l-[#E85D2A] hover:shadow-md"
                            >
                                <div className="text-[9px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                    {m.label}
                                </div>
                                <div className="mt-0.5 font-display text-xl font-semibold tabular-nums text-slate-900">
                                    {m.value}
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Actions */}
                {actions.length > 0 && (
                    <div className="mt-7 flex flex-wrap items-center gap-2.5 border-t border-orange-100/80 pt-6">
                        {actions.map((a, i) => (
                            <ActionButton
                                key={a.id || i}
                                act={a}
                                idx={i}
                                msgIdx={msgIdx}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
