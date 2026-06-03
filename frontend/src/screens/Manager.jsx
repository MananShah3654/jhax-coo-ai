import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useCooChat } from "@/hooks/useCooChat";
import { api } from "@/lib/api";
import Layout from "@/components/Layout";
import DecisionCard from "@/components/DecisionCard";
import { Send, Loader2 } from "lucide-react";
import { toast } from "sonner";

const PREFILL_KEY = "manager_prefill";

const DEFAULT_PROMPT =
    "What should my managers focus on today? Give me prioritised tasks per branch.";

export default function Manager() {
    const location = useLocation();
    const [reply, setReply] = useState(null);
    const [busy, setBusy] = useState(false);
    const [prefillContext, setPrefillContext] = useState(null);
    const { send } = useCooChat();

    // Honor any prefill (from notify action button)
    useEffect(() => {
        let pre = location.state?.prefill;
        if (!pre) {
            try {
                pre = JSON.parse(sessionStorage.getItem(PREFILL_KEY) || "null");
            } catch {
                pre = null;
            }
        }
        if (pre && (pre.message || pre.branch || pre.label)) {
            setPrefillContext(pre);
            try { sessionStorage.removeItem(PREFILL_KEY); } catch {}
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const generate = async () => {
        setBusy(true);
        setReply(null);
        const q = prefillContext
            ? `Build a manager task plan for branch "${prefillContext.branch || "all branches"}". ` +
              `Focus: ${prefillContext.message || prefillContext.label || "improving performance"}.`
            : DEFAULT_PROMPT;
        await send({
            text: q,
            onDelta: ({ reply }) => reply && setReply(reply),
            onComplete: ({ reply }) => reply && setReply(reply),
        });
        setBusy(false);
    };

    // Auto-generate if we arrived with a prefill (one-shot)
    useEffect(() => {
        if (prefillContext && !reply && !busy) {
            generate();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [prefillContext]);

    const notify = async () => {
        try {
            await api.post("/actions/execute", {
                id: "notify_managers",
                kind: "notify",
                label: prefillContext
                    ? `Manager priorities — ${prefillContext.branch || "all branches"}`
                    : "Manager priorities for today",
                payload: prefillContext || {},
            });
            toast.success("Tasks sent to managers");
        } catch {
            toast.error("Notify failed");
        }
    };

    return (
        <Layout>
            <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                Manager Mode
            </div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-900">
                {prefillContext?.branch
                    ? `Tasks for ${prefillContext.branch}`
                    : "What managers should focus on today"}
            </h1>

            {prefillContext && (
                <div className="mt-3 rounded-2xl border border-orange-100 bg-orange-50/50 p-4 text-sm text-slate-700">
                    <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#FF6B35]">
                        Brief from AI COO
                    </div>
                    <p className="mt-0.5">
                        {prefillContext.message || prefillContext.label}
                    </p>
                </div>
            )}

            {!reply && !busy && (
                <div className="mt-6 rounded-3xl border border-dashed border-slate-200 p-10 text-center">
                    <p className="text-sm text-slate-500">
                        Generate AI-curated priorities for every branch
                        manager, ready to send in one tap.
                    </p>
                    <button
                        onClick={generate}
                        disabled={busy}
                        className="mt-5 inline-flex items-center gap-2 rounded-full bg-[#FF6B35] px-6 py-2.5 text-sm font-medium text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] hover:bg-[#E85D2A]"
                    >
                        {busy ? (
                            <Loader2 size={14} className="animate-spin" />
                        ) : (
                            <Send size={14} />
                        )}
                        Generate Manager Plan
                    </button>
                </div>
            )}

            {(reply || busy) && (
                <div className="mt-6 space-y-4">
                    {reply ? (
                        <DecisionCard reply={reply} streaming={busy} />
                    ) : (
                        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-400">
                            <Loader2 size={14} className="mr-2 inline animate-spin text-[#FF6B35]" />
                            Drafting manager plan…
                        </div>
                    )}
                    <div className="flex flex-wrap gap-2">
                        <button
                            data-testid="manager-send"
                            onClick={notify}
                            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
                        >
                            <Send size={14} /> Send to All Managers
                        </button>
                        <button
                            onClick={generate}
                            disabled={busy}
                            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                        >
                            Re-generate
                        </button>
                    </div>
                </div>
            )}
        </Layout>
    );
}
