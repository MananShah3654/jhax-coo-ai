import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Send, AlertTriangle, Plus, Trash2, MessageSquare, X, Menu as MenuIcon, Sparkles, ArrowUpRight } from "lucide-react";
import { API } from "@/lib/api";
import Layout from "@/components/Layout";
import DecisionCard from "@/components/DecisionCard";
import VoiceMic from "@/components/VoiceMic";
import { useCooChat } from "@/hooks/useCooChat";
import { useChatHistory } from "@/hooks/useChatHistory";
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

function relativeTime(ts) {
    const s = Math.floor((Date.now() - ts) / 1000);
    if (s < 60) return "just now";
    if (s < 3600) return `${Math.floor(s / 60)}m`;
    if (s < 86400) return `${Math.floor(s / 3600)}h`;
    return `${Math.floor(s / 86400)}d`;
}

function HistorySidebar({
    index,
    activeId,
    onNew,
    onOpen,
    onDelete,
    onClearAll,
    open,
    onClose,
}) {
    return (
        <>
            {/* Mobile overlay */}
            {open && (
                <div
                    onClick={onClose}
                    className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm lg:hidden"
                />
            )}
            <aside
                className={`fixed left-0 top-0 z-40 flex h-full w-72 shrink-0 flex-col border-r border-slate-200 bg-white pt-4 transition-transform duration-300 lg:static lg:translate-x-0 lg:bg-transparent lg:pt-0 ${
                    open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
                }`}
            >
                <div className="flex items-center justify-between gap-2 px-4 pb-3 lg:hidden">
                    <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                        Chat history
                    </div>
                    <button
                        onClick={onClose}
                        className="grid h-8 w-8 place-items-center rounded-full text-slate-500 hover:bg-slate-100"
                    >
                        <X size={14} />
                    </button>
                </div>

                <button
                    data-testid="chat-new"
                    onClick={() => {
                        onNew();
                        onClose?.();
                    }}
                    className="mx-3 mt-1 flex items-center justify-center gap-2 rounded-full bg-[#FF6B35] px-4 py-2.5 text-sm font-medium text-white shadow-[0_4px_14px_rgba(255,107,53,0.35)] hover:bg-[#E85D2A]"
                >
                    <Plus size={14} /> New chat
                </button>

                <div className="mt-4 flex-1 overflow-y-auto px-2">
                    {index.length === 0 && (
                        <div className="px-3 py-6 text-center text-xs text-slate-400">
                            No conversations yet.
                        </div>
                    )}
                    {index.map((s) => (
                        <div
                            key={s.id}
                            data-testid={`chat-session-${s.id}`}
                            className={`group flex items-start gap-2 rounded-xl px-2.5 py-2 transition-colors ${
                                s.id === activeId
                                    ? "bg-orange-50"
                                    : "hover:bg-slate-50"
                            }`}
                        >
                            <button
                                onClick={() => {
                                    onOpen(s.id);
                                    onClose?.();
                                }}
                                className="flex flex-1 items-start gap-2 text-left"
                            >
                                <MessageSquare
                                    size={14}
                                    className={`mt-0.5 shrink-0 ${
                                        s.id === activeId
                                            ? "text-[#FF6B35]"
                                            : "text-slate-400"
                                    }`}
                                />
                                <div className="min-w-0 flex-1">
                                    <div
                                        className={`truncate text-sm ${
                                            s.id === activeId
                                                ? "font-semibold text-[#E85D2A]"
                                                : "text-slate-800"
                                        }`}
                                    >
                                        {s.title}
                                    </div>
                                    <div className="text-[10px] uppercase tracking-[0.15em] text-slate-400">
                                        {relativeTime(s.updatedAt || s.createdAt)}
                                    </div>
                                </div>
                            </button>
                            <button
                                data-testid={`chat-delete-${s.id}`}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onDelete(s.id);
                                }}
                                className="grid h-7 w-7 shrink-0 place-items-center rounded-full text-slate-300 opacity-0 transition-opacity hover:bg-red-50 hover:text-red-500 group-hover:opacity-100"
                                title="Delete"
                            >
                                <Trash2 size={12} />
                            </button>
                        </div>
                    ))}
                </div>

                {index.length > 0 && (
                    <button
                        data-testid="chat-clear-all"
                        onClick={() => {
                            if (window.confirm("Clear all chats? This cannot be undone."))
                                onClearAll();
                        }}
                        className="m-3 rounded-xl border border-slate-200 px-3 py-2 text-xs font-medium text-slate-500 hover:border-red-200 hover:text-red-500"
                    >
                        Clear all conversations
                    </button>
                )}
            </aside>
        </>
    );
}

export default function Chat() {
    const location = useLocation();
    const initialQ = location.state?.question;

    const {
        index,
        activeId,
        messages,
        setMessages,
        newChat,
        openChat,
        deleteChat,
        clearAll,
        ensureSession,
    } = useChatHistory();

    const [input, setInput] = useState("");
    const [voicePlaying, setVoicePlaying] = useState(null);
    const [sidebarOpen, setSidebarOpen] = useState(false);
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
        ensureSession();
        const aiIdx = messages.length + 1;
        setMessages((m) => [
            ...m,
            { role: "user", text: q },
            { role: "ai", reply: null, streaming: true, raw: "" },
        ]);
        scroll();
        await send({
            text: q,
            onDelta: ({ reply, rawText }) => {
                setMessages((m) => {
                    const cp = [...m];
                    if (cp[aiIdx])
                        cp[aiIdx] = { ...cp[aiIdx], reply, raw: rawText };
                    return cp;
                });
                scroll();
            },
            onComplete: ({ reply, rawText }) => {
                setMessages((m) => {
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
            // Always start a fresh chat when coming from "Ask Anything"
            newChat();
            // small defer so newChat state lands before ask
            setTimeout(() => ask(initialQ), 0);
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
            <div className="-mx-4 -my-6 flex h-[calc(100vh-4rem)] lg:-mx-6 lg:-my-10 lg:h-[calc(100vh)]">
                <HistorySidebar
                    index={index}
                    activeId={activeId}
                    onNew={newChat}
                    onOpen={openChat}
                    onDelete={deleteChat}
                    onClearAll={clearAll}
                    open={sidebarOpen}
                    onClose={() => setSidebarOpen(false)}
                />

                <div className="relative flex flex-1 flex-col">
                    {/* Top bar */}
                    <div className="sticky top-0 z-20 flex items-center justify-between gap-2 border-b border-slate-200/70 bg-white/80 px-4 py-3 backdrop-blur-xl lg:px-8">
                        <div className="flex items-center gap-2">
                            <button
                                data-testid="chat-sidebar-toggle"
                                onClick={() => setSidebarOpen((v) => !v)}
                                className="grid h-9 w-9 place-items-center rounded-full text-slate-600 hover:bg-slate-100 lg:hidden"
                            >
                                <MenuIcon size={16} />
                            </button>
                            <div>
                                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-slate-400">
                                    AI COO Chat
                                </div>
                                <h1 className="font-display text-xl font-semibold tracking-tight text-slate-900">
                                    {index.find((s) => s.id === activeId)?.title ||
                                        "Ask Anything"}
                                </h1>
                            </div>
                        </div>
                    </div>

                    {/* Stream */}
                    <div
                        data-testid={TID.chatStream}
                        className="flex-1 overflow-y-auto px-4 pb-40 pt-6 lg:px-8"
                    >
                        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
                            {messages.length === 0 && (
                                <div className="fade-up mx-auto mt-8 max-w-2xl text-center">
                                    <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-[#FF6B35] to-[#E85D2A] text-white shadow-[0_8px_24px_rgba(255,107,53,0.35)]">
                                        <Sparkles size={22} />
                                    </div>
                                    <h2 className="mt-5 font-display text-3xl font-semibold tracking-tight text-slate-900">
                                        What would you like to know?
                                    </h2>
                                    <p className="mx-auto mt-2 max-w-md text-[15px] leading-relaxed text-slate-500">
                                        Ask about revenue, customers, menu, or operations —
                                        one question, one answer, one action.
                                    </p>
                                    <div className="mt-7 grid gap-2.5 text-left sm:grid-cols-2">
                                        {[
                                            "How is my business today?",
                                            "Why are sales down?",
                                            "Which branch is underperforming?",
                                            "Create a combo for slow lunch hours",
                                            "What are my busiest hours?",
                                            "Forecast revenue for next 30 days",
                                        ].map((s) => (
                                            <button
                                                key={s}
                                                onClick={() => ask(s)}
                                                className="group flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3.5 text-left text-sm text-slate-700 shadow-[0_1px_3px_rgba(15,23,42,0.03)] transition-all duration-200 hover:-translate-y-0.5 hover:border-[#FF6B35]/50 hover:text-[#E85D2A] hover:shadow-[0_10px_24px_rgba(15,23,42,0.06)]"
                                            >
                                                <span>{s}</span>
                                                <ArrowUpRight
                                                    size={15}
                                                    className="shrink-0 text-slate-300 transition-colors group-hover:text-[#FF6B35]"
                                                />
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {messages.map((m, i) =>
                                m.role === "user" ? (
                                    <UserBubble key={i} text={m.text} idx={i} />
                                ) : (
                                    <div key={i} className="flex justify-start">
                                        {m.reply ? (
                                            <DecisionCard
                                                reply={m.reply}
                                                streaming={m.streaming}
                                                msgIdx={i}
                                                onSuggestion={(s) => ask(s)}
                                                onPlayVoice={
                                                    m.streaming || m.reply.clarify
                                                        ? null
                                                        : () =>
                                                              playVoice(
                                                                  i,
                                                                  [
                                                                      m.reply.status,
                                                                      m.reply.reason,
                                                                      m.reply.opportunity,
                                                                  ]
                                                                      .filter(Boolean)
                                                                      .join(". ")
                                                              )
                                                }
                                                voicePlaying={voicePlaying === i}
                                            />
                                        ) : (
                                            <div className="fade-up flex items-center gap-3 rounded-3xl rounded-tl-md border border-slate-200/70 bg-white px-6 py-5 shadow-[0_2px_18px_rgba(15,23,42,0.04)]">
                                                <div className="flex gap-1">
                                                    <span className="h-2 w-2 animate-bounce rounded-full bg-[#FF6B35] [animation-delay:-0.3s]" />
                                                    <span className="h-2 w-2 animate-bounce rounded-full bg-[#FF6B35] [animation-delay:-0.15s]" />
                                                    <span className="h-2 w-2 animate-bounce rounded-full bg-[#FF6B35]" />
                                                </div>
                                                <span className="text-sm text-slate-400">
                                                    Reading your restaurant's data…
                                                </span>
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
                    </div>

                    {/* Composer */}
                    <div className="absolute inset-x-0 bottom-12 z-30 px-4 lg:bottom-6 lg:px-8">
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
                </div>
            </div>
        </Layout>
    );
}
