import { createContext, useContext, useEffect, useRef, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { api } from "@/lib/api";
import {
    auth as fbAuth,
    firebaseEnabled,
    emailSignIn,
    emailRegister,
    customTokenSignIn,
    firebaseSignOut,
} from "@/lib/firebase";

const AuthCtx = createContext(null);

// Auth = Firebase (email/password + phone). On top of a persisted Firebase
// session we add a PIN "quick unlock":
//   - first login  → set a PIN (POST /me/pin)
//   - later visits → the session is restored but "locked"; a correct PIN
//                    (POST /me/pin/verify) unlocks without a full login
//   - forgot PIN / expired session → fall back to full email/phone login
export function AuthProvider({ children }) {
    const [fbUser, setFbUser] = useState(null);
    const [profile, setProfile] = useState(null);
    const [ready, setReady] = useState(!firebaseEnabled);
    // "unlocked" means identity was proven THIS page-load (fresh login or PIN).
    const [unlocked, setUnlocked] = useState(false);
    // Set when the user taps "Forgot PIN" — forces the set-PIN screen after the
    // fallback full login so they can choose a new one.
    const [forcePinSetup, setForcePinSetup] = useState(false);
    // True only when a full sign-in happened in this session (vs. a restored
    // session on page load) — lets us skip the PIN lock right after logging in.
    const freshLoginRef = useRef(false);

    useEffect(() => {
        if (!firebaseEnabled || !fbAuth) return;
        const unsub = onAuthStateChanged(fbAuth, async (user) => {
            setFbUser(user);
            if (user) {
                try {
                    const { data } = await api.get("/me");
                    setProfile(data);
                } catch {
                    setProfile(null);
                }
                // Fresh login → already proven; restored session stays locked.
                if (freshLoginRef.current) {
                    setUnlocked(true);
                    freshLoginRef.current = false;
                }
            } else {
                setProfile(null);
                setUnlocked(false);
            }
            setReady(true);
        });
        return unsub;
    }, []);

    const refreshProfile = async () => {
        const { data } = await api.get("/me");
        setProfile(data);
        return data;
    };

    const updateProfile = async (fields) => {
        const { data } = await api.patch("/me", fields);
        setProfile(data);
        return data;
    };

    // --- Full login (email / phone) ---
    // On success we mark the session "active" (unlocked) directly, in addition
    // to the freshLoginRef path — so proceeding never depends on onAuthStateChanged
    // firing again (it may not if the same user is re-authenticated).
    const loginWithEmail = async (email, password) => {
        freshLoginRef.current = true;
        const res = await emailSignIn(email, password);
        setUnlocked(true);
        return res;
    };
    const registerWithEmail = async (email, password) => {
        freshLoginRef.current = true;
        const res = await emailRegister(email, password);
        setUnlocked(true);
        return res;
    };
    // Phone OTP via Twilio Verify (backend), then finish with a Firebase custom
    // token. Same freshLoginRef + setUnlocked handshake as email login, so the
    // React Router auth-flow gate triggers identically after phone login.
    const sendPhoneOtp = async (e164Phone) => {
        const { data } = await api.post("/auth/send-otp", { phone_number: e164Phone });
        return data; // { status, to }
    };
    const verifyPhoneOtp = async (e164Phone, code) => {
        freshLoginRef.current = true;
        const { data } = await api.post("/auth/verify-otp", {
            phone_number: e164Phone,
            code,
        });
        const res = await customTokenSignIn(data.token);
        setUnlocked(true);
        return res;
    };

    // --- PIN quick-unlock ---
    const setPin = async (pin) => {
        const { data } = await api.post("/me/pin", { pin });
        setProfile((p) => ({ ...(p || {}), has_pin: true }));
        setForcePinSetup(false);
        setUnlocked(true);
        return data;
    };

    // Throws Error with .code =
    //   "wrong"   → PIN didn't match (403)
    //   "expired" → session/token gone (401); we log out for a full re-login
    //   "error"   → server down / network / 400 no-PIN — NOT the user's fault,
    //               so the UI must not blame their PIN.
    const verifyPin = async (pin) => {
        try {
            await api.post("/me/pin/verify", { pin });
            setUnlocked(true);
        } catch (e) {
            const status = e?.response?.status;
            if (status === 401) {
                await logout(); // session/token dead → force full login
                const err = new Error("expired");
                err.code = "expired";
                throw err;
            }
            const err = new Error(status === 403 ? "wrong" : "error");
            err.code = status === 403 ? "wrong" : "error";
            throw err;
        }
    };

    // "Forgot PIN" → drop the session and require a new PIN after re-login.
    const forgotPin = async () => {
        setForcePinSetup(true);
        await logout();
    };

    const logout = async () => {
        if (firebaseEnabled) await firebaseSignOut();
        setFbUser(null);
        setProfile(null);
        setUnlocked(false);
    };

    const auth = fbUser ? { mode: "firebase", user: profile } : null;
    // A session only counts as "active" (allowed into onboarding / the app) when
    // identity was proven THIS page-load — either a fresh login (unlocked) or a
    // complete account with a PIN to unlock. A cold-restored, not-yet-finished
    // session (no PIN, mid-onboarding) is NOT active: the user must log in first,
    // so we never auto-redirect a freshly-opened app straight to /onboarding.
    const sessionActive = Boolean(
        fbUser && (unlocked || (profile && profile.has_pin))
    );
    const needsOnboarding = Boolean(
        fbUser && (!profile || !profile.restaurant_name)
    );
    const needsPinSetup = Boolean(
        fbUser && profile && (!profile.has_pin || forcePinSetup)
    );
    // After onboarding + PIN, a first-time user must "connect" a POS (which
    // seeds their demo data). pos_provider stays NULL until they pick one.
    const needsPosSetup = Boolean(
        fbUser && profile && profile.restaurant_name && profile.has_pin
        && !forcePinSetup && !profile.pos_provider
    );
    const locked = Boolean(
        fbUser && profile && profile.has_pin && !unlocked && !forcePinSetup
    );

    return (
        <AuthCtx.Provider
            value={{
                auth,
                ready,
                firebaseEnabled,
                fbUser,
                profile,
                sessionActive,
                needsOnboarding,
                needsPinSetup,
                needsPosSetup,
                locked,
                loginWithEmail,
                registerWithEmail,
                sendPhoneOtp,
                verifyPhoneOtp,
                setPin,
                verifyPin,
                forgotPin,
                refreshProfile,
                updateProfile,
                logout,
            }}
        >
            {children}
        </AuthCtx.Provider>
    );
}

export const useAuth = () => useContext(AuthCtx);
