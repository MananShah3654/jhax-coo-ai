import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { api } from "@/lib/api";
import { TID } from "@/constants/testIds";

/**
 * Voice mic with waveform UI.
 * - Records audio via MediaRecorder (webm/opus)
 * - Posts to /api/ai/transcribe (Whisper)
 * - Calls `onTranscribed(text)` on success
 *
 * Props:
 *   size: 'hero' | 'inline'
 */
export default function VoiceMic({
    onTranscribed,
    size = "hero",
    disabled = false,
    testId = TID.micButton,
}) {
    const [state, setState] = useState("idle"); // idle | recording | transcribing
    const [error, setError] = useState(null);
    const mediaRef = useRef(null);
    const chunksRef = useRef([]);

    const stop = () => {
        if (mediaRef.current && mediaRef.current.state !== "inactive") {
            mediaRef.current.stop();
        }
    };

    const start = async () => {
        setError(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: true,
            });
            const mr = new MediaRecorder(stream, {
                mimeType: "audio/webm;codecs=opus",
            });
            chunksRef.current = [];
            mr.ondataavailable = (e) =>
                e.data.size && chunksRef.current.push(e.data);
            mr.onstop = async () => {
                stream.getTracks().forEach((t) => t.stop());
                const blob = new Blob(chunksRef.current, {
                    type: "audio/webm",
                });
                setState("transcribing");
                try {
                    const form = new FormData();
                    form.append("file", blob, "voice.webm");
                    const { data } = await api.post(
                        "/ai/transcribe",
                        form,
                        {
                            headers: { "Content-Type": "multipart/form-data" },
                        }
                    );
                    onTranscribed?.(data.text || "");
                } catch (e) {
                    setError("Transcription failed. Try again.");
                } finally {
                    setState("idle");
                }
            };
            mediaRef.current = mr;
            mr.start();
            setState("recording");
        } catch (e) {
            setError(
                "Microphone permission denied. Please enable mic access."
            );
            setState("idle");
        }
    };

    useEffect(
        () => () => mediaRef.current && mediaRef.current.state !== "inactive" && mediaRef.current.stop(),
        []
    );

    const isHero = size === "hero";
    const btnSize = isHero ? "w-28 h-28" : "w-12 h-12";
    const iconSize = isHero ? 36 : 18;

    return (
        <div className="flex flex-col items-center gap-3">
            <button
                data-testid={
                    state === "recording" ? TID.micStopButton : testId
                }
                disabled={disabled || state === "transcribing"}
                onClick={state === "recording" ? stop : start}
                className={`${btnSize} grid place-items-center rounded-full text-white transition-transform duration-200 ${
                    state === "recording"
                        ? "mic-glow scale-105"
                        : "hover:scale-105"
                } disabled:opacity-40 disabled:cursor-not-allowed`}
                style={{
                    background:
                        "linear-gradient(180deg,#FF6B35 0%, #E85D2A 100%)",
                    boxShadow:
                        "0 14px 32px rgba(255,107,53,0.35), 0 0 60px rgba(255,107,53,0.25)",
                }}
                aria-label={
                    state === "recording" ? "Stop recording" : "Start voice"
                }
            >
                {state === "transcribing" ? (
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-white border-r-transparent" />
                ) : state === "recording" ? (
                    <Square size={iconSize} fill="white" />
                ) : (
                    <Mic size={iconSize} />
                )}
            </button>

            {state === "recording" && (
                <div className="flex h-7 items-center gap-1">
                    {[0, 1, 2, 3, 4, 5, 6].map((i) => (
                        <span
                            key={i}
                            className="bar block w-[3px] rounded-full"
                            style={{
                                height: 22,
                                animationDelay: `${i * 90}ms`,
                            }}
                        />
                    ))}
                </div>
            )}
            {state === "idle" && isHero && (
                <div className="text-xs uppercase tracking-[0.25em] text-slate-400">
                    Tap to ask
                </div>
            )}
            {state === "transcribing" && (
                <div
                    data-testid={TID.transcriptPreview}
                    className="text-xs text-slate-500"
                >
                    Transcribing…
                </div>
            )}
            {error && (
                <div className="max-w-xs text-center text-xs text-red-500">
                    {error}
                </div>
            )}
        </div>
    );
}
