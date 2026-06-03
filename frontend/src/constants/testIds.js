// Centralised data-testid constants for QA / e2e.
export const TID = {
    // Auth
    pinDigit: (d) => `pin-digit-${d}`,
    pinBackspace: "pin-backspace",
    pinClear: "pin-clear",
    pinError: "pin-error",
    pinLogout: "logout-btn",

    // Layout
    navHome: "nav-home",
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
};
