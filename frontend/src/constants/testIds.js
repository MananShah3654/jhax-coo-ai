// Centralised data-testid constants for QA / e2e.
export const TID = {
    // Auth
    pinDigit: (d) => `pin-digit-${d}`,
    pinBackspace: "pin-backspace",
    pinClear: "pin-clear",
    pinError: "pin-error",
    pinLogout: "logout-btn",

    // Auth — Firebase email/phone login
    authTabEmail: "auth-tab-email",
    authTabPhone: "auth-tab-phone",
    authTabPin: "auth-tab-pin",
    authEmailInput: "auth-email-input",
    authPasswordInput: "auth-password-input",
    authEmailSubmit: "auth-email-submit",
    authRegisterToggle: "auth-register-toggle",
    authPhoneInput: "auth-phone-input",
    authPhoneSendOtp: "auth-phone-send-otp",
    authOtpInput: "auth-otp-input",
    authOtpVerify: "auth-otp-verify",
    authError: "auth-error",

    // Auth — onboarding (fill profile after first sign-in)
    onboardName: "onboard-name-input",
    onboardRestaurant: "onboard-restaurant-input",
    onboardContact: "onboard-contact-input",
    onboardSubmit: "onboard-submit",

    // Auth — PIN quick-unlock
    setPinDigit: (d) => `set-pin-digit-${d}`,
    setPinContinue: "set-pin-continue",
    setPinError: "set-pin-error",
    unlockDigit: (d) => `unlock-digit-${d}`,
    unlockSubmit: "unlock-submit",
    unlockError: "unlock-error",
    unlockForgot: "unlock-forgot",

    // Layout
    campCopyWhatsapp: "camp-copy-whatsapp",
    campCopyCaption: "camp-copy-caption",
    campDownloadInstagram: "camp-download-instagram",
    campBannerReady: "camp-banner-ready",

    navHome: "nav-home",
    navKpis: "nav-kpis",
    navChat: "nav-chat",
    navBranches: "nav-branches",
    navCustomers: "nav-customers",
    navMenu: "nav-menu",
    navMarketing: "nav-marketing",
    navForecast: "nav-forecast",
    navManager: "nav-manager",

    // Home
    kpiRevenue: "kpi-revenue",
    kpiOrders: "kpi-orders",
    kpiAov: "kpi-aov",
    kpiTips: "kpi-tips",
    kpiCustomers: "kpi-customers",
    kpiCovers: "kpi-covers",
    kpiCartAbandon: "kpi-cart-abandon",
    kpiRepeat: "kpi-repeat",
    kpiDiscount: "kpi-discount",
    kpiTurnover: "kpi-turnover",
    kpiRevpash: "kpi-revpash",
    healthRing: "health-ring",
    briefingCard: "briefing-card",
    briefingLaunchBtn: "briefing-launch-campaign",
    briefingShareBtn: "briefing-share-report",

    // Ask anything / mic
    askInput: "ask-anything-input",
    askSubmit: "ask-anything-submit",
    micButton: "mic-button",
    micStopButton: "mic-stop-button",
    transcriptPreview: "voice-transcript",

    // Chat
    chatMessage: (i) => `chat-msg-${i}`,
    chatStream: "chat-stream",
    chatInput: "chat-input",
    chatSend: "chat-send",
    chatMic: "chat-mic",
    chatPlay: (i) => `chat-tts-play-${i}`,
    chatActionBtn: (i, id) => `chat-action-${i}-${id}`,

    // Branches
    branchRow: (id) => `branch-row-${id}`,

    // Marketing
    campAudience: "camp-audience",
    campChannel: "camp-channel",
    campGoal: "camp-goal",
    campGenerate: "camp-generate",
    campResult: "camp-result",
    campBannerDesc: "camp-banner-desc",
    campBannerGenerate: "camp-banner-generate",
    campBannerImg: "camp-banner-img",
    campBannerRegenerate: "camp-banner-regenerate",
    comboGenerate: "combo-generate",
    comboResult: "combo-result",
    comboRegenerate: "combo-regenerate",
    comboLaunch: "combo-launch",
};
