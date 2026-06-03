import { useState } from "react";
import {
    Megaphone,
    Share2,
    ArrowUpRight,
    Bell,
    Sparkles,
    FileText,
    Volume2,
    Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { TID } from "@/constants/testIds";

const KIND_META = {
    campaign: { Icon: Megaphone, cls: "bg-[#FF6B35] text-white hover:bg-[#e85d2a]" },
    share:    { Icon: Share2,    cls: "bg-slate-900 text-white hover:bg-slate-800" },
    navigate: { Icon: ArrowUpRight, cls: "bg-slate-100 text-slate-900 hover:bg-slate-200" },
    notify:   { Icon: Bell,      cls: "bg-amber-500 text-white hover:bg-amber-600" },
    promotion:{ Icon: Sparkles,  cls: "bg-[#FF6B35] text-white hover:bg-[#e85d2a]" },
    report:   { Icon: FileText,  cls: "bg-slate-900 text-white hover:bg-slate-800" },
};

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
 * Renders an executive Decision Card from the AI JSON reply.
 */
export default function DecisionCard({
    reply,
    streaming = false,
    msgIdx,
    onPlayVoice,
    voicePlaying = false,
}) {
    if (!reply) return null;
    const {
        status,
        reason,
        opportunity,
        action,
        expected_impact,
        metrics = [],
        actions = [],
    } = reply;
    return (
        <div className="fade-up relative w-full overflow-hidden rounded-3xl rounded-tl-md border border-slate-200/70 bg-white p-7 shadow-[0_2px_18px_rgba(15,23,42,0.04)]">
            {/* Orange accent bar */}
            <div className="absolute left-0 top-0 h-full w-1 bg-gradient-to-b from-[#FF6B35] to-[#E85D2A]" />
            <div className="space-y-5 pl-2">
                {/* Status */}
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                            Status
                        </div>
                        <h3 className="mt-1 font-display text-2xl font-semibold leading-tight tracking-tight text-slate-900">
                            {status}
                            {streaming && <span className="caret" />}
                        </h3>
                    </div>
                    {onPlayVoice && (
                        <button
                            data-testid={TID.chatPlay(msgIdx ?? 0)}
                            onClick={onPlayVoice}
                            className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200"
                            title="Read aloud"
                        >
                            {voicePlaying ? (
                                <Loader2 size={14} className="animate-spin" />
                            ) : (
                                <Volume2 size={14} />
                            )}
                        </button>
                    )}
                </div>

                {/* Metrics */}
                {metrics.length > 0 && (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                        {metrics.map((m, i) => (
                            <div
                                key={i}
                                className="rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-2"
                            >
                                <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                                    {m.label}
                                </div>
                                <div className="mt-0.5 font-display text-lg font-semibold text-slate-900">
                                    {m.value}
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Reason */}
                {reason && (
                    <div>
                        <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                            Reason
                        </div>
                        <p className="mt-1 border-l-2 border-slate-200 pl-3 text-[15px] leading-relaxed text-slate-700">
                            {reason}
                        </p>
                    </div>
                )}

                {/* Opportunity */}
                {opportunity && (
                    <div className="rounded-xl bg-orange-50/60 p-4">
                        <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                            Opportunity
                        </div>
                        <p className="mt-1 text-[15px] leading-relaxed text-slate-800">
                            {opportunity}
                        </p>
                    </div>
                )}

                {/* Action + impact */}
                {(action || expected_impact) && (
                    <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-slate-100 pt-4">
                        <div>
                            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                                Recommended Action
                            </div>
                            <div className="mt-1 max-w-2xl text-[15px] font-medium text-slate-900">
                                {action}
                            </div>
                        </div>
                        {expected_impact && (
                            <div className="text-right">
                                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                                    Expected Impact
                                </div>
                                <div className="mt-1 font-mono text-lg font-semibold text-emerald-600">
                                    {expected_impact}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Actions */}
                {actions.length > 0 && (
                    <div className="flex flex-wrap items-center gap-2 pt-1">
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
