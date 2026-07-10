// Firebase Web SDK initialization for client-side login (email + phone).
//
// Config comes from REACT_APP_FIREBASE_* env vars (see frontend/.env). If they
// aren't set yet, `firebaseEnabled` is false and the app falls back to the demo
// PIN login — nothing here throws, so the UI still runs before Firebase is set up.
import { initializeApp } from "firebase/app";
import {
    getAuth,
    RecaptchaVerifier,
    signInWithEmailAndPassword,
    createUserWithEmailAndPassword,
    signInWithPhoneNumber,
    signOut,
} from "firebase/auth";

const cfg = {
    apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
    authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
    appId: process.env.REACT_APP_FIREBASE_APP_ID,
};

// Considered configured only when the essential keys are present.
export const firebaseEnabled = Boolean(cfg.apiKey && cfg.authDomain && cfg.projectId);

let app = null;
let auth = null;
if (firebaseEnabled) {
    app = initializeApp(cfg);
    auth = getAuth(app);
} else {
    // eslint-disable-next-line no-console
    console.warn(
        "[firebase] REACT_APP_FIREBASE_* not set — email/phone login disabled, " +
            "using demo PIN. Fill frontend/.env and restart to enable."
    );
}

export { auth };

// --- Email / password ---
export const emailSignIn = (email, password) =>
    signInWithEmailAndPassword(auth, email, password);

export const emailRegister = (email, password) =>
    createUserWithEmailAndPassword(auth, email, password);

// --- Phone (OTP) ---
// Firebase requires a reCAPTCHA verifier anchored to a DOM node for phone auth.
// We keep a single invisible verifier per page load.
let recaptcha = null;
export function getRecaptcha(containerId = "recaptcha-container") {
    if (!auth) throw new Error("Firebase is not configured");
    if (!recaptcha) {
        recaptcha = new RecaptchaVerifier(auth, containerId, { size: "invisible" });
    }
    return recaptcha;
}

// Send an OTP SMS; returns a confirmationResult with .confirm(code).
export const phoneSendOtp = (e164Phone, containerId) =>
    signInWithPhoneNumber(auth, e164Phone, getRecaptcha(containerId));

export const firebaseSignOut = () => (auth ? signOut(auth) : Promise.resolve());
