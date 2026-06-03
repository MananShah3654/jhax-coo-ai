/**
 * Persistent chat history (localStorage-backed) — ChatGPT-style.
 *
 * Each session = { id, title, createdAt, messages: [{role, text?, reply?, raw?}] }
 *
 * Stored under "jhapay_coo_chats". The full list of sessions sits in
 * "jhapay_coo_chats_index" so we can render the sidebar without loading
 * every message body.
 */
import { useCallback, useEffect, useState } from "react";

const INDEX_KEY = "jhapay_coo_chats_index";
const SESSION_KEY = (id) => `jhapay_coo_chat_${id}`;

function readIndex() {
    try {
        return JSON.parse(localStorage.getItem(INDEX_KEY)) || [];
    } catch {
        return [];
    }
}
function writeIndex(arr) {
    try {
        localStorage.setItem(INDEX_KEY, JSON.stringify(arr));
    } catch {}
}
function readSession(id) {
    try {
        return JSON.parse(localStorage.getItem(SESSION_KEY(id))) || null;
    } catch {
        return null;
    }
}
function writeSession(s) {
    try {
        localStorage.setItem(SESSION_KEY(s.id), JSON.stringify(s));
    } catch {}
}
function removeSession(id) {
    try {
        localStorage.removeItem(SESSION_KEY(id));
    } catch {}
}

function makeId() {
    return (
        Date.now().toString(36) + Math.random().toString(36).slice(2, 7)
    );
}

const DEFAULT_TITLE = "New chat";

function deriveTitle(messages) {
    const firstUser = messages.find((m) => m.role === "user" && m.text);
    if (!firstUser) return DEFAULT_TITLE;
    const t = firstUser.text.trim();
    return t.length > 56 ? t.slice(0, 53) + "…" : t;
}

export function useChatHistory() {
    const [index, setIndex] = useState(() => readIndex());
    const [activeId, setActiveId] = useState(() => readIndex()[0]?.id || null);
    const [messages, setMessages] = useState(() => {
        const first = readIndex()[0];
        return first ? readSession(first.id)?.messages || [] : [];
    });

    // Persist messages whenever they change (only if there's an active session)
    useEffect(() => {
        if (!activeId) return;
        const session = readSession(activeId) || {
            id: activeId,
            title: DEFAULT_TITLE,
            createdAt: Date.now(),
            messages: [],
        };
        session.messages = messages;
        session.title = deriveTitle(messages);
        writeSession(session);
        // Update index entry
        setIndex((prev) => {
            const next = prev.filter((x) => x.id !== activeId);
            next.unshift({
                id: activeId,
                title: session.title,
                createdAt: session.createdAt,
                updatedAt: Date.now(),
                count: messages.length,
            });
            writeIndex(next);
            return next;
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [messages, activeId]);

    const newChat = useCallback(() => {
        const id = makeId();
        const s = {
            id,
            title: DEFAULT_TITLE,
            createdAt: Date.now(),
            messages: [],
        };
        writeSession(s);
        setIndex((prev) => {
            const next = [
                { id, title: s.title, createdAt: s.createdAt, updatedAt: s.createdAt, count: 0 },
                ...prev,
            ];
            writeIndex(next);
            return next;
        });
        setActiveId(id);
        setMessages([]);
        return id;
    }, []);

    const openChat = useCallback((id) => {
        const s = readSession(id);
        if (!s) return;
        setActiveId(id);
        setMessages(s.messages || []);
    }, []);

    const deleteChat = useCallback(
        (id) => {
            removeSession(id);
            setIndex((prev) => {
                const next = prev.filter((x) => x.id !== id);
                writeIndex(next);
                return next;
            });
            if (id === activeId) {
                const remaining = readIndex().filter((x) => x.id !== id);
                if (remaining.length) {
                    openChat(remaining[0].id);
                } else {
                    setActiveId(null);
                    setMessages([]);
                }
            }
        },
        [activeId, openChat]
    );

    const clearAll = useCallback(() => {
        index.forEach((x) => removeSession(x.id));
        writeIndex([]);
        setIndex([]);
        setActiveId(null);
        setMessages([]);
    }, [index]);

    // If no session exists at all, lazily create one when the user sends a message
    const ensureSession = useCallback(() => {
        if (activeId) return activeId;
        return newChat();
    }, [activeId, newChat]);

    return {
        index,
        activeId,
        messages,
        setMessages,
        newChat,
        openChat,
        deleteChat,
        clearAll,
        ensureSession,
    };
}
