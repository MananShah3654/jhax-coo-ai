import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Send, AlertTriangle } from "lucide-react";
import { API } from "@/lib/api";
import Layout from "@/components/Layout";
import DecisionCard from "@/components/DecisionCard";
import VoiceMic from "@/components/VoiceMic";
import { useCooChat } from "@/hooks/useCooChat";
import { TID } from "@/constants/testIds";

function UserBubble({ text, idx }) {
    return (
        <div
            data-testid={TID.chatMessage(idx)}
            className="fade-up flex justify-end"
        >
            <div className="max-w-[80%] rounded-3xl rounded-tr-md bg-slate-900 px-5 py-3 text-[15px] leading-relaxed text-white">
                {text}
            </div>
        </div>
    );
}

export default function Chat() {
    const location = useLocation();
    const initialQ = location.state?.question;

    const [msgs, setMsgs] = useState([]); // [{role:'user'|'ai', text?, reply?, streaming?, raw?}]
    const [input, setInput] = useState("");
    const [voicePlaying, setVoicePlaying] = useState(null);
    const audioRef = useRef(null);
    const endRef = useRef(null);
    const initialFiredRef = useRef(false);
    const { streaming, error, send } = useCooChat();

    const scroll = () =>
        setTimeout(
            () => endRef.current?.scrollIntoView({ behavior: "smooth" }),
            50
        );

    const ask = async (text) => {
        const q = (text || input).trim();
        if (!q || streaming) return;
        setInput("");
        const aiIdx = msgs.length + 1;
        setMsgs((m) => [
            ...m,
            { role: "user", text: q },
            { role: "ai", reply: null, streaming: true, raw: "" },
        ]);
        scroll();
        await send({
            text: q,
            onDelta: ({ reply, rawText }) => {
                setMsgs((m) => {
                    const cp = [...m];
                    if (cp[aiIdx])
                        cp[aiIdx] = {
                            ...cp[aiIdx],
                            reply,
                            raw: rawText,
                        };
                    return cp;
                });
                scroll();
            },
            onComplete: ({ reply, rawText }) => {
                setMsgs((m) => {
                    const cp = [...m];
                    if (cp[aiIdx])
                        cp[aiIdx] = {
                            ...cp[aiIdx],
                            reply,
                            raw: rawText,
                            streaming: false,
                        };
                    return cp;
                });
                scroll();
            },
        });
    };

    // Auto-fire question from Home navigation (guarded against StrictMode double-effect)
    useEffect(() => {
        if (initialQ && !initialFiredRef.current) {
            initialFiredRef.current = true;
            ask(initialQ);
            window.history.replaceState({}, "");
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const playVoice = async (idx, text) => {
        if (!text) return;
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current = null;
        }
        setVoicePlaying(idx);
        try {
            const res = await fetch(`${API}/ai/tts`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text: text.slice(0, 3500), voice: "nova" }),
            });
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = new Audio(url);
            audioRef.current = a;
            a.onended = () => setVoicePlaying(null);
            await a.play();
        } catch {
            setVoicePlaying(null);
        }
    };

    return (
        <Layout>
            <div className="mb-4">
                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                    AI COO Chat
                </div>
                <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight text-slate-900">
                    Ask Anything
                </h1>
            </div>

            <div
                data-testid={TID.chatStream}
                className="mx-auto flex w-full max-w-4xl flex-col gap-6 pb-44"
            >
                {msgs.length === 0 && (
                    <div className="rounded-3xl border border-dashed border-slate-200 p-10 text-center">
                        <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                            Try
                        </div>
                        <div className="mt-2 grid gap-2 sm:grid-cols-2">
                            {[
                                "How is my business today?",
                                "Why are sales down?",
                                "Which branch is underperforming?",
                                "Create a campaign for inactive customers",
                                "What are my busiest hours?",
                                "Forecast revenue for next 30 days",
                            ].map((s) => (
                                <button
                                    key={s}
                                    onClick={() => ask(s)}
                                    className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 hover:border-[#FF6B35] hover:text-[#E85D2A]"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {msgs.map((m, i) =>
                    m.role === "user" ? (
                        <UserBubble key={i} text={m.text} idx={i} />
                    ) : (
                        <div key={i} className="flex justify-start">
                            {m.reply ? (
                                <DecisionCard
                                    reply={m.reply}
                                    streaming={m.streaming}
                                    msgIdx={i}
                                    onPlayVoice={
                                        m.streaming
                                            ? null
                                            : () =>
                                                  playVoice(
                                                      i,
                                                      [
                                                          m.reply.status,
                                                          m.reply.reason,
                                                          m.reply.opportunity,
                                                          m.reply.action,
                                                      ]
                                                          .filter(Boolean)
                                                          .join(". ")
                                                  )
                                    }
                                    voicePlaying={voicePlaying === i}
                                />
                            ) : (
                                <div className="rounded-3xl border border-slate-200 bg-white p-6">
                                    <div className="flex items-center gap-2 text-sm text-slate-400">
                                        <span className="h-2 w-2 animate-pulse rounded-full bg-[#FF6B35]" />
                                        Thinking…
                                    </div>
                                </div>
                            )}
                        </div>
                    )
                )}

                {error && (
                    <div className="flex items-center gap-2 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-600">
                        <AlertTriangle size={14} /> {error}
                    </div>
                )}

                <div ref={endRef} />
            </div>

            {/* Sticky composer */}
            <div className="fixed inset-x-0 bottom-12 z-40 px-4 lg:bottom-6 lg:left-64">
                <div className="mx-auto flex w-full max-w-3xl items-center gap-2 rounded-full border border-slate-200 bg-white p-1.5 shadow-[0_12px_40px_rgba(15,23,42,0.08)]">
                    <div className="pl-2">
                        <VoiceMic
                            size="inline"
                            disabled={streaming}
                            testId={TID.chatMic}
                            onTranscribed={(t) => t && ask(t)}
                        />
                    </div>
                    <input
                        data-testid={TID.chatInput}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && ask()}
                        placeholder={
                            streaming
                                ? "AI COO is replying…"
                                : "Ask your restaurant anything…"
                        }
                        disabled={streaming}
                        className="flex-1 bg-transparent px-3 py-2.5 text-[15px] text-slate-900 placeholder:text-slate-400 focus:outline-none disabled:opacity-50"
                    />
                    <button
                        data-testid={TID.chatSend}
                        onClick={() => ask()}
                        disabled={!input.trim() || streaming}
                        className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-[#FF6B35] text-white shadow-[0_4px_14px_rgba(255,107,53,0.4)] transition-all hover:bg-[#E85D2A] disabled:opacity-40"
                    >
                        <Send size={16} />
                    </button>
                </div>
            </div>
        </Layout>
    );
}
