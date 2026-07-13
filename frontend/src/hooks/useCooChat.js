import { useState, useCallback, useRef } from "react";
import { API, authHeader } from "@/lib/api";

/**
 * Hook that streams the AI COO reply from /api/ai/chat (SSE).
 * Buffers the full streaming text and on-the-fly attempts to parse the
 * structured Decision Card JSON so the UI can render progressively.
 */

const FENCE_RE = /^```(?:json)?\s*|\s*```$/gim;

function stripFences(s) {
    return s.replace(FENCE_RE, "").trim();
}

function safeParseJson(buf) {
    const s = stripFences(buf || "").trim();
    if (!s) return null;
    try {
        return JSON.parse(s);
    } catch {
        // Try to grab the first balanced object
        const start = s.indexOf("{");
        if (start < 0) return null;
        let depth = 0;
        for (let i = start; i < s.length; i++) {
            if (s[i] === "{") depth++;
            else if (s[i] === "}") {
                depth--;
                if (depth === 0) {
                    try {
                        return JSON.parse(s.slice(start, i + 1));
                    } catch {
                        return null;
                    }
                }
            }
        }
        return null;
    }
}

/**
 * Extract any partial values from a streaming JSON buffer using simple
 * regex - so the UI can render the headline even before JSON is closed.
 */
function partialExtract(buf) {
    const s = stripFences(buf || "");
    const grab = (key) => {
        const re = new RegExp(`"${key}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)`, "i");
        const m = re.exec(s);
        if (!m) return undefined;
        try {
            return JSON.parse(`"${m[1]}"`);
        } catch {
            return m[1];
        }
    };
    return {
        status: grab("status"),
        clarify: grab("clarify"),
        reason: grab("reason"),
        opportunity: grab("opportunity"),
        action: grab("action"),
        expected_impact: grab("expected_impact"),
    };
}

export function useCooChat(initialSession = null) {
    const [sessionId, setSessionId] = useState(initialSession);
    const [streaming, setStreaming] = useState(false);
    const [error, setError] = useState(null);
    const abortRef = useRef(null);

    const send = useCallback(
        async ({ text, onDelta, onComplete }) => {
            setError(null);
            setStreaming(true);
            const ctrl = new AbortController();
            abortRef.current = ctrl;
            try {
                // /ai/chat is a protected route; attach the Firebase token
                // (raw fetch bypasses the axios interceptor in lib/api).
                const auth = await authHeader();
                const res = await fetch(`${API}/ai/chat`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json", ...auth },
                    body: JSON.stringify({
                        session_id: sessionId,
                        message: text,
                    }),
                    signal: ctrl.signal,
                });
                if (!res.body) throw new Error("No stream");
                const reader = res.body.getReader();
                const dec = new TextDecoder();
                let sseBuf = "";
                let textBuf = "";

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    sseBuf += dec.decode(value, { stream: true });
                    let idx;
                    while ((idx = sseBuf.indexOf("\n\n")) !== -1) {
                        const raw = sseBuf.slice(0, idx);
                        sseBuf = sseBuf.slice(idx + 2);
                        const lines = raw.split("\n");
                        let event = "message";
                        let data = "";
                        for (const ln of lines) {
                            if (ln.startsWith("event:"))
                                event = ln.slice(6).trim();
                            else if (ln.startsWith("data:"))
                                data += ln.slice(5).trim();
                        }
                        if (event === "session") {
                            try {
                                setSessionId(JSON.parse(data).session_id);
                            } catch {}
                        } else if (event === "delta") {
                            try {
                                const parsed = JSON.parse(data);
                                textBuf += parsed.text || "";
                                const reply =
                                    safeParseJson(textBuf) ||
                                    partialExtract(textBuf);
                                onDelta?.({ rawText: textBuf, reply });
                            } catch {}
                        } else if (event === "done") {
                            const reply =
                                safeParseJson(textBuf) ||
                                partialExtract(textBuf);
                            onComplete?.({ rawText: textBuf, reply });
                        } else if (event === "error") {
                            try {
                                setError(JSON.parse(data).message);
                            } catch {
                                setError("AI error");
                            }
                        }
                    }
                }
                // Final flush
                const reply = safeParseJson(textBuf) || partialExtract(textBuf);
                onComplete?.({ rawText: textBuf, reply });
            } catch (e) {
                if (e.name !== "AbortError") setError(e.message || "Stream error");
            } finally {
                setStreaming(false);
                abortRef.current = null;
            }
        },
        [sessionId]
    );

    const cancel = useCallback(() => {
        abortRef.current?.abort();
    }, []);

    return { sessionId, setSessionId, streaming, error, send, cancel };
}
