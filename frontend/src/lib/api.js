import axios from "axios";
import { auth as fbAuth } from "@/lib/firebase";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

// Current Firebase ID token, or null if signed out. Use for raw fetch() calls
// (e.g. SSE streaming) that don't go through the axios `api` instance.
export async function authHeader() {
    try {
        const user = fbAuth?.currentUser;
        if (user) {
            const token = await user.getIdToken();
            return { Authorization: `Bearer ${token}` };
        }
    } catch {
        // ignore — caller proceeds unauthenticated
    }
    return {};
}

// Attach the current Firebase ID token (if signed in) so the backend can
// verify it on protected routes like /me. No-op for the demo PIN flow.
api.interceptors.request.use(async (config) => {
    try {
        const user = fbAuth?.currentUser;
        if (user) {
            const token = await user.getIdToken();
            config.headers.Authorization = `Bearer ${token}`;
        }
    } catch {
        // ignore — request proceeds unauthenticated
    }
    return config;
});

export const fmtUsd = (n) =>
    typeof n === "number"
        ? n.toLocaleString("en-US", {
              style: "currency",
              currency: "USD",
              maximumFractionDigits: 0,
          })
        : n;

export const fmtUsdCents = (n) =>
    typeof n === "number"
        ? n.toLocaleString("en-US", {
              style: "currency",
              currency: "USD",
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
          })
        : n;

export const fmtPct = (n, withSign = true) => {
    if (typeof n !== "number") return n;
    const s = `${n > 0 && withSign ? "+" : ""}${n.toFixed(1)}%`;
    return s;
};
