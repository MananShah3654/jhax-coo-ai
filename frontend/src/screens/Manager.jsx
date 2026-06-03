import { useState } from "react";
import { useCooChat } from "@/hooks/useCooChat";
import { api } from "@/lib/api";
import Layout from "@/components/Layout";
import DecisionCard from "@/components/DecisionCard";
import { Send, Loader2 } from "lucide-react";
import { toast } from "sonner";

const QUESTION =
    "What should my managers focus on today? Give me prioritised tasks per branch.";

export default function Manager() {
    const [reply, setReply] = useState(null);
    const [busy, setBusy] = useState(false);
    const { send } = useCooChat();

    const generate = async () => {
        setBusy(true);
        setReply(null);
        await send({
            text: QUESTION,
            onDelta: ({ reply }) => reply && setReply(reply),
            onComplete: ({ reply }) => reply && setReply(reply),
        });
        setBusy(false);
    };

    const notify = async () => {
        try {
            await api.post("/actions/execute", {
                id: "notify_managers",
                kind: "notify",
                label: "Manager priorities for today",
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
                What managers should focus on today
            </h1>

            {!reply && (
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

            {reply && (
                <div className="mt-6 space-y-4">
                    <DecisionCard reply={reply} streaming={busy} />
                    <div className="flex flex-wrap gap-2">
                        <button
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
