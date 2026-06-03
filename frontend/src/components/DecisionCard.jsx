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
            // Persist prefill so /marketing can pick it up
            try {
                sessionStorage.setItem(
                    "campaign_prefill",
                    JSON.stringify(act.prefill || {})
                );
            } catch {}
            navigate("/marketing", { state: { prefill: act.prefill || {} } });
            return;
        }
        if (act.kind === "share") {
            const t = SHARE_TYPES.has(act.target) ? act.target : "daily";
            openShareModal(t);
            return;
        }
        if (act.kind === "report") {
            openShareModal(SHARE_TYPES.has(act.target) ? act.target : "daily");
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
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-all ${meta.cls} disabled:opacity-60`}
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
            <div className="fade-up w-full max-w-2xl rounded-3xl rounded-tl-md border border-slate-200/70 bg-white p-6 shadow-[0_2px_18px_rgba(15,23,42,0.04)]">
                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                    Need a bit more
                </div>
                <p className="mt-1 font-display text-xl font-semibold leading-snug tracking-tight text-slate-900">
                    {reply.clarify}
                    {streaming && <span className="caret" />}
                </p>
                {Array.isArray(reply.suggestions) && reply.suggestions.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-2">
                        {reply.suggestions.map((s, i) => (
                            <button
                                key={i}
                                data-testid={`clarify-suggestion-${i}`}
                                onClick={() => onSuggestion?.(s)}
                                className="rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:border-[#FF6B35] hover:text-[#E85D2A]"
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
        <div className="fade-up relative w-full overflow-hidden rounded-3xl rounded-tl-md border border-slate-200/70 bg-white p-6 shadow-[0_2px_18px_rgba(15,23,42,0.04)]">
            <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-[#FF6B35] to-[#E85D2A]" />

            <div className="pl-2">
                {/* Hero status + impact pill + voice button */}
                <div className="flex items-start justify-between gap-3">
                    <h3 className="font-display text-2xl font-semibold leading-tight tracking-tight text-slate-900">
                        {status}
                        {streaming && <span className="caret" />}
                    </h3>
                    <div className="flex shrink-0 items-center gap-2">
                        {expected_impact && (
                            <span className="rounded-full bg-emerald-50 px-3 py-1 font-mono text-xs font-semibold text-emerald-600">
                                {expected_impact}
                            </span>
                        )}
                        {onPlayVoice && (
                            <button
                                data-testid={TID.chatPlay(msgIdx ?? 0)}
                                onClick={onPlayVoice}
                                className="grid h-8 w-8 place-items-center rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200"
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
                    <p className="mt-2 text-[15px] leading-relaxed text-slate-600">
                        {reason}
                        {reason && opportunity && (
                            <span className="text-slate-400"> &nbsp;·&nbsp; </span>
                        )}
                        {opportunity && (
                            <span className="text-slate-700">{opportunity}</span>
                        )}
                    </p>
                )}

                {/* Metrics chips */}
                {metrics.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-2">
                        {metrics.map((m, i) => (
                            <div
                                key={i}
                                className="rounded-lg bg-slate-50 px-3 py-1.5"
                            >
                                <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                    {m.label}{" "}
                                </span>
                                <span className="ml-1 font-display text-sm font-semibold text-slate-900">
                                    {m.value}
                                </span>
                            </div>
                        ))}
                    </div>
                )}

                {/* Actions */}
                {actions.length > 0 && (
                    <div className="mt-5 flex flex-wrap items-center gap-2">
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
