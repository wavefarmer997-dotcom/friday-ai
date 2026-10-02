/**
 * Friday - Frontend Real-time WebSocket & Memory UI Controller
 */

let ws = null;
let isConnected = false;
let currentBotBubble = null;
let currentBotContent = "";
let isTtsEnabled = true;
let isRecording = false;
let recognition = null;
let isMemoryPanelOpen = window.innerWidth > 900;

// Voice Call Mode Variables
let isInVoiceCall = false;
let isCallMicMuted = false;
let callState = "idle"; // "listening" | "thinking" | "speaking"

// Image Gen Variables
let selectedImageStyle = "photorealistic";
let selectedImageRatio = "1:1";

// DOM Elements
const messagesContainer = document.getElementById("messagesContainer");
const welcomeCard = document.getElementById("welcomeCard");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const voiceBtn = document.getElementById("voiceBtn");
const connectionStatus = document.getElementById("connectionStatus");
const connectionText = document.getElementById("connectionText");
const memoryToast = document.getElementById("memoryToast");
const toastDesc = document.getElementById("toastDesc");
const memoryPanel = document.getElementById("memoryPanel");
const memoryBackdrop = document.getElementById("memoryBackdrop");
const memoryList = document.getElementById("memoryList");
const memoryCountBadge = document.getElementById("memoryCountBadge");
const toggleMemoryBtn = document.getElementById("toggleMemoryBtn");
const closeMemoryBtn = document.getElementById("closeMemoryBtn");
const toggleTtsBtn = document.getElementById("toggleTtsBtn");
const openSettingsBtn = document.getElementById("openSettingsBtn");
const settingsModal = document.getElementById("settingsModal");
const addMemoryModal = document.getElementById("addMemoryModal");
const addMemoryModalBtn = document.getElementById("addMemoryModalBtn");
const clearAllMemoriesBtn = document.getElementById("clearAllMemoriesBtn");
const clearChatBtn = document.getElementById("clearChatBtn");

// Voice Call & Image Gen DOM Elements
const startVoiceCallBtn = document.getElementById("startVoiceCallBtn");
const voiceCallOverlay = document.getElementById("voiceCallOverlay");
const callVoiceOrb = document.getElementById("callVoiceOrb");
const callStatusBadge = document.getElementById("callStatusBadge");
const callStatusText = document.getElementById("callStatusText");
const callUserSpeech = document.getElementById("callUserSpeech");
const callBotSpeech = document.getElementById("callBotSpeech");
const callMuteMicBtn = document.getElementById("callMuteMicBtn");
const openImageModalBtn = document.getElementById("openImageModalBtn");
const imageGenModal = document.getElementById("imageGenModal");
const imagePromptInput = document.getElementById("imagePromptInput");
const submitImageGenBtn = document.getElementById("submitImageGenBtn");
const imageLightbox = document.getElementById("imageLightbox");
const lightboxImg = document.getElementById("lightboxImg");
const lightboxCaption = document.getElementById("lightboxCaption");
const lightboxDownloadBtn = document.getElementById("lightboxDownloadBtn");

const installPwaBtn = document.getElementById("installPwaBtn");
let deferredInstallPrompt = null;

// ==================== Initialize Application ====================

document.addEventListener("DOMContentLoaded", () => {
    // Initial collapse on mobile / small screens
    if (!isMemoryPanelOpen && memoryPanel) {
        memoryPanel.classList.add("collapsed");
    }
    initWebSocket();
    initSpeechRecognition();
    fetchMemories();
    fetchSettings();
    setupEventListeners();
    initPwaInstall();
});

function setMemoryPanelState(open) {
    isMemoryPanelOpen = open;
    if (memoryPanel) {
        memoryPanel.classList.toggle("collapsed", !isMemoryPanelOpen);
    }
    if (memoryBackdrop) {
        memoryBackdrop.classList.toggle("active", isMemoryPanelOpen && window.innerWidth <= 900);
    }
}

function initPwaInstall() {
    // 1. ลงทะเบียน Service Worker สำหรับ PWA
    if ("serviceWorker" in navigator) {
        window.addEventListener("load", () => {
            navigator.serviceWorker.register("/static/service-worker.js")
                .then((reg) => console.log("[PWA] Service Worker registered:", reg.scope))
                .catch((err) => console.warn("[PWA] Service Worker registration failed:", err));
        });
    }

    // 2. ดักจับ Event สำหรับปุ่ม "ติดตั้งแอป" บน Android / Chrome
    window.addEventListener("beforeinstallprompt", (e) => {
        e.preventDefault();
        deferredInstallPrompt = e;
        if (installPwaBtn) {
            installPwaBtn.style.display = "inline-flex";
            installPwaBtn.classList.add("glow-pulse");
        }
    });

    if (installPwaBtn) {
        installPwaBtn.addEventListener("click", async () => {
            if (deferredInstallPrompt) {
                deferredInstallPrompt.prompt();
                const { outcome } = await deferredInstallPrompt.userChoice;
                console.log("[PWA] Install prompt outcome:", outcome);
                deferredInstallPrompt = null;
                installPwaBtn.style.display = "none";
            } else {
                alert("สำหรับติดตั้งบน Android: แตะที่เมนู 3 จุด (⋮) มุมขวาบนของ Google Chrome แล้วเลือก 'เพิ่มลงในหน้าจอหลัก' หรือ 'ติดตั้งแอป' ได้เลยค่ะ!");
            }
        });
    }

    window.addEventListener("appinstalled", () => {
        console.log("[PWA] Friday App Installed Successfully!");
        if (installPwaBtn) installPwaBtn.style.display = "none";
    });
}

function setupEventListeners() {
    // Input Auto-grow & Enter to Send
    messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    messageInput.addEventListener("input", () => {
        messageInput.style.height = "auto";
        messageInput.style.height = Math.min(messageInput.scrollHeight, 140) + "px";
    });

    sendBtn.addEventListener("click", sendMessage);

    // Toggle Memory Panel
    if (toggleMemoryBtn) {
        toggleMemoryBtn.addEventListener("click", () => {
            setMemoryPanelState(!isMemoryPanelOpen);
        });
    }

    if (closeMemoryBtn) {
        closeMemoryBtn.addEventListener("click", () => {
            setMemoryPanelState(false);
        });
    }

    if (memoryBackdrop) {
        memoryBackdrop.addEventListener("click", () => {
            setMemoryPanelState(false);
        });
    }

    // Toggle TTS
    toggleTtsBtn.addEventListener("click", () => {
        isTtsEnabled = !isTtsEnabled;
        toggleTtsBtn.querySelector("i").className = isTtsEnabled ? "fa-solid fa-volume-high" : "fa-solid fa-volume-xmark";
        toggleTtsBtn.querySelector(".btn-label").textContent = `เสียงอ่าน: ${isTtsEnabled ? "เปิด" : "ปิด"}`;
        if (!isTtsEnabled) stopCurrentSpeech();
    });

    // Voice Input Button
    voiceBtn.addEventListener("click", toggleVoiceRecording);

    // Settings Modal
    openSettingsBtn.addEventListener("click", openSettingsModal);
    document.getElementById("saveSettingsBtn").addEventListener("click", saveSettings);
    document.getElementById("settingProvider").addEventListener("change", handleProviderChange);
    document.getElementById("toggleKeyVisibility").addEventListener("click", toggleApiKeyVisibility);
    const togglePolKeyBtn = document.getElementById("togglePollinationsKeyVisibility");
    if (togglePolKeyBtn) {
        togglePolKeyBtn.addEventListener("click", togglePollinationsKeyVisibility);
    }
    const btnSyncObsidian = document.getElementById("btnSyncObsidianNow");
    if (btnSyncObsidian) {
        btnSyncObsidian.addEventListener("click", syncObsidianNow);
    }
    const btnGitPush = document.getElementById("btnGitPushNow");
    if (btnGitPush) {
        btnGitPush.addEventListener("click", pushGithubNow);
    }

    // Quick Action Pills
    const quickActionPills = document.getElementById("quickActionPills");
    if (quickActionPills) {
        quickActionPills.addEventListener("click", (e) => {
            const btn = e.target.closest(".pill-btn");
            if (!btn) return;
            handleQuickAction(btn.dataset.action);
        });
    }

    // Add Memory Modal
    addMemoryModalBtn.addEventListener("click", () => {
        addMemoryModal.classList.add("active");
    });
    document.getElementById("saveNewMemoryBtn").addEventListener("click", saveNewMemory);

    // Clear Memories
    clearAllMemoriesBtn.addEventListener("click", async () => {
        if (confirm("คุณต้องการล้างความจำทั้งหมดของ Friday หรือไม่?")) {
            await fetch("/api/memories/clear", { method: "POST" });
            fetchMemories();
        }
    });

    // Clear Chat
    clearChatBtn.addEventListener("click", async () => {
        if (confirm("คุณต้องการล้างข้อความในห้องแชทหรือไม่?")) {
            await fetch("/api/history/clear", { method: "POST" });
            messagesContainer.innerHTML = "";
            if (welcomeCard) messagesContainer.appendChild(welcomeCard);
        }
    });

    // Voice Call Button
    if (startVoiceCallBtn) {
        startVoiceCallBtn.addEventListener("click", startVoiceCall);
    }

    // Image Generation Studio Buttons
    if (openImageModalBtn) {
        openImageModalBtn.addEventListener("click", openImageModal);
    }
    if (submitImageGenBtn) {
        submitImageGenBtn.addEventListener("click", submitImageGen);
    }
    const sendImageToChatBtn = document.getElementById("sendImageToChatBtn");
    if (sendImageToChatBtn) {
        sendImageToChatBtn.addEventListener("click", sendGeneratedImageToChat);
    }
    const randomPromptBtn = document.getElementById("randomPromptBtn");
    if (randomPromptBtn) {
        randomPromptBtn.addEventListener("click", pickRandomPrompt);
    }

    // Preset Style & Ratio Selectors
    document.querySelectorAll(".style-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            document.querySelectorAll(".style-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            selectedImageStyle = chip.getAttribute("data-style");
        });
    });

    document.querySelectorAll(".ratio-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            document.querySelectorAll(".ratio-chip").forEach(c => c.classList.remove("active"));
            chip.classList.add("active");
            selectedImageRatio = chip.getAttribute("data-ratio");
        });
    });
}

// ==================== WebSocket Real-time Connection ====================

function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/chat`;

    connectionText.textContent = "กำลังเชื่อมต่อ...";
    connectionStatus.className = "status-indicator";

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        isConnected = true;
        connectionStatus.className = "status-indicator online";
        connectionText.textContent = "ออนไลน์ • เรียลไทม์";
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
    };

    ws.onclose = () => {
        isConnected = false;
        connectionStatus.className = "status-indicator";
        connectionText.textContent = "การเชื่อมต่อหลุด - กำลังลองใหม่...";
        setTimeout(initWebSocket, 2500);
    };

    ws.onerror = (err) => {
        console.error("WebSocket Error:", err);
    };
}

function handleServerEvent(data) {
    switch (data.type) {
        case "stream_start":
            if (welcomeCard && welcomeCard.parentElement) {
                welcomeCard.style.display = "none";
            }
            currentBotContent = "";
            currentBotBubble = createBotMessageElement();
            break;

        case "stream_chunk":
            if (currentBotBubble) {
                currentBotContent += data.chunk;
                updateBotContent(currentBotBubble, currentBotContent, true);
                scrollToBottom();
            }
            if (isInVoiceCall && callBotSpeech) {
                const cleanDisplay = cleanTextForSpeech(currentBotContent);
                if (cleanDisplay) {
                    callBotSpeech.textContent = cleanDisplay;
                }
            }
            break;

        case "stream_end":
            if (currentBotBubble) {
                updateBotContent(currentBotBubble, data.full_reply, false);
                scrollToBottom();
            }
            currentBotBubble = null;

            if (isInVoiceCall) {
                setCallVisualState("speaking", "Friday กำลังตอบกลับ...");
                speakText(data.full_reply, () => {
                    if (isInVoiceCall && !isCallMicMuted) {
                        triggerCallListening();
                    }
                });
            } else if (isTtsEnabled) {
                speakText(data.full_reply);
            }
            break;

        case "memory_learned":
            showMemoryLearnedToast(data.items);
            renderMemoriesList(data.all_memories);
            break;

        case "error":
            alert("ข้อผิดพลาด: " + data.message);
            break;
    }
}

// ==================== Message Rendering ====================

function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || !isConnected) return;

    if (welcomeCard && welcomeCard.parentElement) {
        welcomeCard.style.display = "none";
    }

    // Render User Message Bubble
    createUserMessageElement(text);
    messageInput.value = "";
    messageInput.style.height = "auto";
    scrollToBottom();

    // Send through WebSocket
    ws.send(JSON.stringify({
        type: "message",
        content: text,
        session_id: "default"
    }));
}

function quickSend(text) {
    messageInput.value = text;
    sendMessage();
}

function createUserMessageElement(text) {
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `
        <div class="message-bubble">${escapeHtml(text)}</div>
    `;
    messagesContainer.appendChild(row);
}

function createBotMessageElement() {
    const row = document.createElement("div");
    row.className = "message-row bot";
    row.innerHTML = `
        <div class="message-avatar"><i class="fa-solid fa-brain"></i></div>
        <div class="message-bubble streaming-cursor">
            <span class="bubble-text"></span>
            <div class="message-toolbar" style="display: none;">
                <button class="msg-tool-btn copy-btn" title="คัดลอกข้อความ"><i class="fa-regular fa-copy"></i> คัดลอก</button>
                <button class="msg-tool-btn speak-btn" title="อ่านออกเสียง"><i class="fa-solid fa-volume-high"></i> ฟังเสียง</button>
            </div>
        </div>
    `;
    messagesContainer.appendChild(row);
    return row;
}

function updateBotContent(botRow, content, isStreaming) {
    const bubble = botRow.querySelector(".message-bubble");
    const textSpan = botRow.querySelector(".bubble-text");
    const toolbar = botRow.querySelector(".message-toolbar");

    if (isStreaming) {
        textSpan.innerHTML = formatMarkdown(content);
        bubble.classList.add("streaming-cursor");
    } else {
        bubble.classList.remove("streaming-cursor");
        textSpan.innerHTML = formatMarkdown(content);
        
        // ตรวจสอบและเพิ่มประสิทธิภาพรูปภาพในข้อความแชท
        const imgs = textSpan.querySelectorAll("img");
        imgs.forEach(img => {
            img.style.cursor = "pointer";
            img.title = "คลิกเพื่อขยายดูภาพขนาดเต็ม";
            img.onclick = () => {
                if (window.openImageLightbox) {
                    window.openImageLightbox(img.src, img.alt || "รูปภาพจาก Friday AI");
                }
            };
            img.onerror = function() {
                if (!this.dataset.retried) {
                    this.dataset.retried = "1";
                    const originalSrc = this.src;
                    setTimeout(() => {
                        if (!originalSrc.includes("/api/image-proxy") && originalSrc.startsWith("http")) {
                            this.src = `/api/image-proxy?url=${encodeURIComponent(originalSrc)}`;
                        } else {
                            const sep = originalSrc.includes("?") ? "&" : "?";
                            this.src = originalSrc + sep + "_retry=" + Date.now();
                        }
                    }, 1500);
                }
            };
        });

        if (toolbar) {
            toolbar.style.display = "flex";
            const copyBtn = toolbar.querySelector(".copy-btn");
            const speakBtn = toolbar.querySelector(".speak-btn");
            
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(content);
                copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> คัดลอกแล้ว';
                setTimeout(() => copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> คัดลอก', 2000);
            };

            speakBtn.onclick = () => speakText(content);
        }
    }
}

function formatMarkdown(text) {
    if (typeof marked !== "undefined") {
        return marked.parse(text);
    }
    return escapeHtml(text).replace(/\n/g, "<br>");
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function scrollToBottom(force = false) {
    if (!messagesContainer) return;
    const threshold = 160;
    const isNearBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop - messagesContainer.clientHeight <= threshold;
    if (force || isNearBottom) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

function handleQuickAction(action) {
    if (!messageInput) return;
    if (action === "search") {
        messageInput.value = "ค้นหาข้อมูลล่าสุดเรื่อง: ";
        messageInput.focus();
    } else if (action === "deep_think") {
        messageInput.value = "ช่วยวิเคราะห์เชิงลึกและแจกแจงกระบวนการคิดเรื่อง: ";
        messageInput.focus();
    } else if (action === "draw") {
        openImageModal();
    } else if (action === "memory") {
        messageInput.value = "Friday จำข้อมูลอะไรเกี่ยวกับผมได้บ้าง ช่วยสรุปข้อมูลให้ฟังหน่อย";
        sendMessage();
    }
}

// ==================== Memory Inspector Panel ====================

async function fetchMemories() {
    try {
        const res = await fetch("/api/memories");
        const data = await res.json();
        renderMemoriesList(data.memories);
    } catch (e) {
        console.error("Failed to fetch memories:", e);
    }
}

function renderMemoriesList(memories) {
    memoryCountBadge.textContent = memories ? memories.length : 0;
    
    if (!memories || memories.length === 0) {
        memoryList.innerHTML = `
            <div class="empty-memory-state">
                <i class="fa-regular fa-folder-open"></i>
                <p>ยังไม่มีข้อมูลในความจำ<br>ลองบอกชื่อหรือเรื่องที่คุณชอบในช่องแชท</p>
            </div>
        `;
        return;
    }

    const categoryLabels = {
        profile: { label: "👤 ข้อมูลส่วนตัว", cls: "profile" },
        preference: { label: "❤️ สิ่งที่ชอบ/ไม่ชอบ", cls: "preference" },
        work: { label: "💼 การงาน", cls: "work" },
        instruction: { label: "📌 คำสั่งพิเศษ", cls: "instruction" },
        general: { label: "💡 ทั่วไป", cls: "general" }
    };

    memoryList.innerHTML = memories.map(m => {
        const cat = categoryLabels[m.category] || categoryLabels.general;
        return `
            <div class="memory-item-card" data-id="${m.id}">
                <div class="memory-card-header">
                    <span class="mem-badge ${cat.cls}">${cat.label}</span>
                    <button class="delete-mem-btn" onclick="deleteMemory(${m.id})" title="ลบข้อมูลนี้">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
                <div class="mem-key">${escapeHtml(m.key_concept)}</div>
                <div class="mem-content">${escapeHtml(m.content)}</div>
            </div>
        `;
    }).join("");
}

async function deleteMemory(id) {
    try {
        const res = await fetch(`/api/memories/${id}`, { method: "DELETE" });
        const data = await res.json();
        renderMemoriesList(data.memories);
    } catch (e) {
        console.error("Failed to delete memory:", e);
    }
}

function showMemoryLearnedToast(items) {
    if (!items || items.length === 0) return;
    const desc = items.map(i => `${i.key}: ${i.value}`).join(", ");
    toastDesc.textContent = desc;
    memoryToast.classList.add("show");
    setTimeout(() => {
        memoryToast.classList.remove("show");
    }, 4500);
}

async function saveNewMemory() {
    const category = document.getElementById("newMemCategory").value;
    const key_concept = document.getElementById("newMemKey").value.trim();
    const content = document.getElementById("newMemContent").value.trim();

    if (!key_concept || !content) {
        alert("กรุณากรอกหัวข้อและรายละเอียด");
        return;
    }

    try {
        const res = await fetch("/api/memories", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ category, key_concept, content, importance: 4 })
        });
        const data = await res.json();
        renderMemoriesList(data.memories);
        closeAddMemoryModal();
        document.getElementById("newMemKey").value = "";
        document.getElementById("newMemContent").value = "";
    } catch (e) {
        alert("เกิดข้อผิดพลาดในการบันทึก");
    }
}

function closeAddMemoryModal() {
    addMemoryModal.classList.remove("active");
}

// ==================== Audio: Speech-to-Text & TTS ====================

function initSpeechRecognition() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        if (voiceBtn) voiceBtn.style.display = "none";
        return;
    }

    recognition = new SpeechRec();
    recognition.lang = "th-TH";
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => {
        isRecording = true;
        if (voiceBtn) {
            voiceBtn.classList.add("recording");
            voiceBtn.title = "กำลังฟังเสียง... (กดอีกครั้งเพื่อหยุด)";
        }
    };

    recognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }
        if (isInVoiceCall) {
            if (callUserSpeech) callUserSpeech.textContent = `🗣️ "${transcript}"`;
        } else {
            messageInput.value = transcript;
        }
    };

    recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        stopRecording();
        if (isInVoiceCall && !isCallMicMuted && callState === "listening") {
            setTimeout(() => {
                if (isInVoiceCall && !isCallMicMuted && callState === "listening") {
                    try { recognition.start(); } catch(e) {}
                }
            }, 600);
        }
    };

    recognition.onend = () => {
        stopRecording();
        if (isInVoiceCall) {
            const raw = callUserSpeech ? (callUserSpeech.textContent || "") : "";
            const said = raw.replace(/^🗣️\s*"/, "").replace(/"$/, "").trim();
            if (said && said.length > 0) {
                setCallVisualState("thinking", "Friday กำลังคิดคำตอบ...");
                if (callUserSpeech) callUserSpeech.textContent = `🗣️ "${said}"`;
                
                // ส่งข้อความประมวลผล
                createUserMessageElement(said);
                scrollToBottom();
                ws.send(JSON.stringify({
                    type: "message",
                    content: said,
                    session_id: "default"
                }));
            } else if (isInVoiceCall && !isCallMicMuted && callState === "listening") {
                setTimeout(() => {
                    if (isInVoiceCall && !isCallMicMuted && callState === "listening") {
                        try { recognition.start(); } catch(e) {}
                    }
                }, 300);
            }
        } else {
            if (messageInput.value.trim().length > 0) {
                sendMessage();
            }
        }
    };
}

function toggleVoiceRecording() {
    if (!recognition) {
        alert("เบราว์เซอร์นี้ไม่รองรับ Speech Recognition แนะนำให้ใช้ Google Chrome หรือ Edge ค่ะ");
        return;
    }
    if (isRecording) {
        recognition.stop();
        stopRecording();
    } else {
        try {
            recognition.start();
        } catch (e) {
            console.error(e);
        }
    }
}

function stopRecording() {
    isRecording = false;
    if (voiceBtn) {
        voiceBtn.classList.remove("recording");
        voiceBtn.title = "กดเพื่อพูดด้วยเสียง (Speech-to-Text)";
    }
}

let currentAudio = null;

function stopCurrentSpeech() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        currentAudio = null;
    }
    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }
}

function cleanTextForSpeech(text) {
    if (!text) return "";
    let clean = text;
    // 1. ตัด Thinking Box และ HTML Tags ทั้งหมด
    clean = clean.replace(/<details[\s\S]*?<\/details>/gi, "");
    clean = clean.replace(/<div[\s\S]*?<\/div>/gi, "");
    clean = clean.replace(/<[^>]+>/g, "");

    // 2. ตัด Markdown Images, Code blocks, Links
    clean = clean.replace(/!\[.*?\]\(.*?\)/g, "");
    clean = clean.replace(/```[\s\S]*?```/g, "");
    clean = clean.replace(/`([^`]+)`/g, "$1");
    clean = clean.replace(/\[(.*?)\]\(.*?\)/g, "$1");

    // 3. ตัดสัญลักษณ์ Markdown
    clean = clean.replace(/[*_#~>•|\-]/g, " ");

    // 4. ตัดตัวอิโมจิ (Emojis) และ Unicode symbols ทุกชนิด
    clean = clean.replace(/\p{Extended_Pictographic}/gu, "");
    clean = clean.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}\u{20E3}\u{E0020}-\u{E007F}]/gu, "");

    // 5. ทำความสะอาดช่องว่าง
    clean = clean.replace(/\s+/g, " ").trim();

    // 6. รองรับความยาวสูงสุด 3,000 ตัวอักษร
    if (clean.length > 3000) {
        clean = clean.substring(0, 3000).trim();
    }
    return clean;
}

function speakText(text, onEnded = null) {
    if (!isTtsEnabled && !isInVoiceCall) {
        if (onEnded) onEnded();
        return;
    }
    stopCurrentSpeech();

    // หากอยู่ในโหมด Voice Call และปิดเสียงลำโพงไว้
    if (isInVoiceCall && isCallSpeakerMuted) {
        if (onEnded) onEnded();
        return;
    }

    const cleanText = cleanTextForSpeech(text);
    if (!cleanText) {
        if (onEnded) onEnded();
        return;
    }

    let hasInvokedEnded = false;
    const finishSpeech = () => {
        if (!hasInvokedEnded) {
            hasInvokedEnded = true;
            if (onEnded) onEnded();
        }
    };

    const audioUrl = `/api/tts?text=${encodeURIComponent(cleanText)}`;
    const audio = new Audio(audioUrl);
    currentAudio = audio;

    audio.onended = () => {
        currentAudio = null;
        finishSpeech();
    };

    audio.onerror = () => {
        currentAudio = null;
        fallbackBrowserTts(cleanText, finishSpeech);
    };

    audio.play().catch((err) => {
        console.warn("Server TTS fallback to browser synthesis:", err);
        fallbackBrowserTts(cleanText, finishSpeech);
    });
}

function fallbackBrowserTts(text, onFinish) {
    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const cleanText = cleanTextForSpeech(text);
        if (!cleanText) {
            if (onFinish) onFinish();
            return;
        }
        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.lang = "th-TH";
        utterance.rate = 1.0;
        utterance.pitch = 1.1;

        const voices = window.speechSynthesis.getVoices();
        const thaiVoices = voices.filter(v => v.lang.includes("th") || v.lang.includes("TH"));
        const maleNames = ["niwat", "male", "man"];
        const femaleNames = ["premwadee", "achara", "kanya", "female", "woman", "girl", "google"];
        const femaleVoice = thaiVoices.find(v => femaleNames.some(n => v.name.toLowerCase().includes(n)))
            || thaiVoices.find(v => !maleNames.some(n => v.name.toLowerCase().includes(n)))
            || thaiVoices[0];

        if (femaleVoice) utterance.voice = femaleVoice;
        utterance.onend = () => { if (onFinish) onFinish(); };
        utterance.onerror = () => { if (onFinish) onFinish(); };
        window.speechSynthesis.speak(utterance);
    } else {
        if (onFinish) onFinish();
    }
}

// ==================== Interactive Voice Call Mode Controller ====================

let callTimerInterval = null;
let callStartTime = 0;
let isCallSpeakerMuted = false;

function startCallTimer() {
    callStartTime = Date.now();
    const timerEl = document.getElementById("callTimer");
    if (timerEl) timerEl.textContent = "00:00";
    clearInterval(callTimerInterval);
    callTimerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - callStartTime) / 1000);
        const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
        const secs = String(elapsed % 60).padStart(2, '0');
        if (timerEl) timerEl.textContent = `${mins}:${secs}`;
    }, 1000);
}

function stopCallTimer() {
    clearInterval(callTimerInterval);
    callTimerInterval = null;
    const timerEl = document.getElementById("callTimer");
    if (timerEl) timerEl.textContent = "00:00";
}

function startVoiceCall() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        alert("เบราว์เซอร์ของคุณยังไม่รองรับ Speech Recognition แนะนำให้ใช้ Google Chrome หรือ Microsoft Edge ค่ะ");
        return;
    }

    isInVoiceCall = true;
    isCallMicMuted = false;
    if (voiceCallOverlay) voiceCallOverlay.classList.add("active");
    stopCurrentSpeech();
    startCallTimer();

    if (callUserSpeech) callUserSpeech.textContent = "";
    if (callBotSpeech) callBotSpeech.textContent = "สวัสดีค่ะ Friday พร้อมคุยแล้วค่ะ...";

    setCallVisualState("speaking", "Friday กำลังทักทาย...");
    speakText("สวัสดีค่ะ Friday พร้อมสนทนาแล้วค่ะ คุณสามารถพูดคุยได้เลยนะคะ", () => {
        if (isInVoiceCall && !isCallMicMuted) {
            triggerCallListening();
        }
    });
}

function endVoiceCall() {
    isInVoiceCall = false;
    stopCallTimer();
    if (voiceCallOverlay) voiceCallOverlay.classList.remove("active");
    stopCurrentSpeech();
    if (recognition && isRecording) {
        recognition.stop();
    }
    setCallVisualState("idle", "สายสิ้นสุดลงแล้ว");
}

function setCallVisualState(state, text) {
    callState = state;
    if (callVoiceOrb) {
        callVoiceOrb.className = "call-orb " + (state !== "idle" ? state : "");
    }
    if (callStatusBadge) {
        callStatusBadge.className = "call-status-badge " + (state !== "idle" ? state : "");
    }
    if (callStatusText) {
        callStatusText.textContent = text;
    }
}

function triggerCallListening() {
    if (!isInVoiceCall || isCallMicMuted) return;

    setCallVisualState("listening", "กำลังฟังคุณพูด... (พูดได้เลยค่ะ)");

    if (!recognition) {
        initSpeechRecognition();
    }

    if (recognition) {
        try {
            recognition.start();
        } catch (e) {
            // Re-arm
        }
    }
}

function handleOrbTap() {
    if (!isInVoiceCall) return;
    if (callState === "speaking") {
        interruptFridaySpeech();
    } else if (callState === "listening") {
        if (recognition) recognition.stop();
    } else {
        triggerCallListening();
    }
}

function interruptFridaySpeech() {
    stopCurrentSpeech();
    setCallVisualState("listening", "รับฟังคุณทันที... (พูดได้เลยค่ะ)");
    triggerCallListening();
}

function toggleCallMic() {
    isCallMicMuted = !isCallMicMuted;
    if (callMuteMicBtn) {
        callMuteMicBtn.classList.toggle("muted", isCallMicMuted);
        callMuteMicBtn.querySelector("i").className = isCallMicMuted ? "fa-solid fa-microphone-slash" : "fa-solid fa-microphone";
    }
    if (isCallMicMuted) {
        if (recognition) recognition.stop();
        setCallVisualState("idle", "ไมโครโฟนถูกปิดอยู่ (กดเพื่อเปิดไมค์)");
    } else {
        triggerCallListening();
    }
}

function toggleCallSpeaker() {
    isCallSpeakerMuted = !isCallSpeakerMuted;
    const btn = document.getElementById("callSpeakerToggleBtn");
    if (btn) {
        btn.classList.toggle("muted", isCallSpeakerMuted);
        btn.querySelector("i").className = isCallSpeakerMuted ? "fa-solid fa-volume-xmark" : "fa-solid fa-volume-high";
    }
    if (isCallSpeakerMuted) {
        stopCurrentSpeech();
    }
}

// ==================== Image Studio & Lightbox ====================

const RANDOM_PROMPTS = [
    "แมวซามูไรในชุดเกราะสีทอง ยืนอยู่ท่ามกลางสวนซากุระเรืองแสงยามค่ำคืน",
    "ห้องแล็บวิทยาศาสตร์แห่งอนาคตสไตล์ Cyberpunk มีโฮโลแกรมลอยตัว แสงนีออนสีฟ้าอมม่วง",
    "ปราสาทลอยฟ้าท่ามกลางหมู่เมฆสีทอง แสงอาทิตย์ยามเย็นส่องประกายเวทมนตร์",
    "หุ่นยนต์สาว Friday นั่งจิบกาแฟริมหน้าต่างยานอวกาศ มองเห็นทางช้างเผือกอันงดงาม",
    "มังกรแก้วคริสตัลเปล่งประกาย ในถ้ำที่เต็มไปด้วยผลึกเพชรและละอองเวทมนตร์",
    "รถสปอร์ตบินได้แห่งอนาคตกำลังแล่นเหนือมหานครนีออนโตเกียวปี 2099",
    "กระต่ายน้อยนักผจญภัยสวมแว่นตาวินเทจกำลังอ่านแผนที่โบราณในป่าลึกลับ",
    "เมืองบาดาลใต้สมุทรเรืองแสงสีมรกต มีปลาวาฬจักรกลแหวกว่ายอย่างสง่างาม"
];

function pickRandomPrompt() {
    const prompt = RANDOM_PROMPTS[Math.floor(Math.random() * RANDOM_PROMPTS.length)];
    if (imagePromptInput) {
        imagePromptInput.value = prompt;
        imagePromptInput.focus();
    }
}

function openImageModal() {
    if (imageGenModal) {
        imageGenModal.classList.add("active");
        if (imagePromptInput) imagePromptInput.focus();
    }
}

function closeImageModal() {
    if (imageGenModal) {
        imageGenModal.classList.remove("active");
    }
}

let lastGeneratedImageData = null;

async function submitImageGen() {
    const prompt = imagePromptInput ? imagePromptInput.value.trim() : "";
    if (!prompt) {
        alert("กรุณากรอกคำอธิบายภาพที่ต้องการให้ Friday วาดค่ะ");
        return;
    }

    const modelSelect = document.getElementById("imageModelSelect");
    const selectedModel = modelSelect ? modelSelect.value : "turbo";

    const resultContainer = document.getElementById("imageGenResult");
    const resultImg = document.getElementById("imageResultImg");
    const resultLoader = document.getElementById("imageResultLoader");
    const downloadBtn = document.getElementById("downloadResultImgBtn");

    if (resultContainer) resultContainer.style.display = "flex";
    if (resultLoader) resultLoader.style.display = "flex";
    if (resultImg) resultImg.style.display = "none";

    if (submitImageGenBtn) {
        submitImageGenBtn.disabled = true;
        submitImageGenBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Friday กำลังวาดภาพ...';
    }

    try {
        const res = await fetch("/api/generate-image", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                prompt: prompt,
                style: selectedImageStyle,
                aspect_ratio: selectedImageRatio,
                model: selectedModel
            })
        });
        const data = await res.json();
        if (res.status === 200 && data.status === "success") {
            lastGeneratedImageData = data;
            if (resultLoader) resultLoader.style.display = "none";
            if (resultImg) {
                resultImg.src = data.image_url;
                resultImg.style.display = "block";
            }
            if (downloadBtn) {
                downloadBtn.href = data.image_url;
                downloadBtn.download = `friday_${data.seed}.jpg`;
                downloadBtn.onclick = (e) => downloadImageDirect(e, data.image_url, `friday_${data.seed}.jpg`);
            }
        } else {
            alert("เกิดข้อผิดพลาดในการสร้างภาพ: " + (data.detail || "ไม่สามารถเชื่อมต่อระบบสร้างภาพได้"));
            if (resultContainer) resultContainer.style.display = "none";
        }
    } catch (err) {
        alert("ข้อผิดพลาดเครือข่าย: " + err.message);
        if (resultContainer) resultContainer.style.display = "none";
    } finally {
        if (submitImageGenBtn) {
            submitImageGenBtn.disabled = false;
            submitImageGenBtn.innerHTML = '<i class="fa-solid fa-sparkles"></i> สั่งวาดรูปภาพทันที';
        }
    }
}

function sendGeneratedImageToChat() {
    if (!lastGeneratedImageData) return;
    const { image_url, original_prompt, english_prompt, seed } = lastGeneratedImageData;

    if (welcomeCard && welcomeCard.parentElement) {
        welcomeCard.style.display = "none";
    }

    const botRow = createBotMessageElement();
    const content = `![${original_prompt}](${image_url})\n\n` +
        `<div class="image-action-bar">\n` +
        `  <a href="${image_url}" target="_blank" class="image-btn download-btn" download="friday_${seed}.jpg" onclick="window.downloadImageDirect(event, '${image_url}', 'friday_${seed}.jpg')"><i class="fa-solid fa-download"></i> ดาวน์โหลดรูปภาพ</a>\n` +
        `  <button type="button" onclick="window.openImageLightbox('${image_url}', '${original_prompt}')" class="image-btn zoom-btn"><i class="fa-solid fa-expand"></i> ขยายดูภาพเต็ม</button>\n` +
        `  <button type="button" onclick="window.useAsPromptTemplate('${original_prompt}')" class="image-btn remix-btn"><i class="fa-solid fa-wand-magic-sparkles"></i> แต่งภาพต่อในสตูดิโอ</button>\n` +
        `</div>\n\n` +
        `✨ **แนวคิดภาพ (Prompt):** *${english_prompt}*`;

    updateBotContent(botRow, content, false);
    scrollToBottom();
    closeImageModal();
}

async function downloadImageDirect(event, url, filename) {
    if (event) event.preventDefault();
    try {
        const response = await fetch(url);
        const blob = await response.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.style.display = "none";
        a.href = blobUrl;
        a.download = filename || "friday_artwork.jpg";
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(blobUrl);
        document.body.removeChild(a);
    } catch (err) {
        window.open(url, "_blank");
    }
}

function useAsPromptTemplate(promptText) {
    if (imagePromptInput) {
        imagePromptInput.value = promptText;
    }
    openImageModal();
}

function openImageLightbox(imageUrl, caption) {
    if (lightboxImg) lightboxImg.src = imageUrl;
    if (lightboxCaption) lightboxCaption.textContent = caption || "Friday AI Artwork";
    if (lightboxDownloadBtn) {
        lightboxDownloadBtn.href = imageUrl;
        lightboxDownloadBtn.onclick = (e) => downloadImageDirect(e, imageUrl, "friday_enlarged.jpg");
    }
    if (imageLightbox) imageLightbox.classList.add("active");
}

function closeImageLightbox(event) {
    if (event && event.target !== imageLightbox && !event.target.closest(".lightbox-close")) {
        return;
    }
    if (imageLightbox) imageLightbox.classList.remove("active");
}

// Window global bindings for inline HTML handlers
window.startVoiceCall = startVoiceCall;
window.endVoiceCall = endVoiceCall;
window.handleOrbTap = handleOrbTap;
window.interruptFridaySpeech = interruptFridaySpeech;
window.toggleCallMic = toggleCallMic;
window.toggleCallSpeaker = toggleCallSpeaker;
window.openImageModal = openImageModal;
window.closeImageModal = closeImageModal;
window.submitImageGen = submitImageGen;
window.sendGeneratedImageToChat = sendGeneratedImageToChat;
window.openImageLightbox = openImageLightbox;
window.closeImageLightbox = closeImageLightbox;
window.downloadImageDirect = downloadImageDirect;
window.useAsPromptTemplate = useAsPromptTemplate;
window.pickRandomPrompt = pickRandomPrompt;
window.togglePollinationsKeyVisibility = togglePollinationsKeyVisibility;

// ==================== Settings Modal & API ====================

async function fetchSettings() {
    try {
        const res = await fetch("/api/settings");
        const data = await res.json();
        document.getElementById("settingProvider").value = data.api_provider;
        document.getElementById("settingModel").value = data.model_name;
        document.getElementById("settingBaseUrl").value = data.openai_base_url;
        document.getElementById("settingPersona").value = data.custom_persona || "";
        if (data.has_api_key) {
            document.getElementById("settingApiKey").placeholder = `ตั้งค่าแล้ว (${data.masked_api_key})`;
        }
        if (data.has_pollinations_key) {
            const polInput = document.getElementById("settingPollinationsKey");
            if (polInput) polInput.placeholder = `ตั้งค่าแล้ว (${data.masked_pollinations_key})`;
        }
        if (data.obsidian_vault_path) {
            const obsPathInput = document.getElementById("settingObsidianPath");
            if (obsPathInput) obsPathInput.value = data.obsidian_vault_path;
        }
        const obsEnabledCheckbox = document.getElementById("settingObsidianEnabled");
        if (obsEnabledCheckbox) {
            obsEnabledCheckbox.checked = !!data.obsidian_sync_enabled;
        }
        const obsBadge = document.getElementById("obsidianStatusBadge");
        if (obsBadge) {
            if (data.obsidian_available) {
                obsBadge.className = "obsidian-badge";
                obsBadge.innerHTML = '<i class="fa-solid fa-circle-check"></i> เชื่อมต่อแล้ว';
            } else {
                obsBadge.className = "obsidian-badge error";
                obsBadge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> ไม่พบโฟลเดอร์';
            }
        }
        if (data.github_remote_url !== undefined) {
            const ghUrlInput = document.getElementById("settingGithubRemoteUrl");
            if (ghUrlInput) ghUrlInput.value = data.github_remote_url || "";
        }
        const ghEnabledCheckbox = document.getElementById("settingGithubEnabled");
        if (ghEnabledCheckbox) {
            ghEnabledCheckbox.checked = !!data.github_sync_enabled;
        }
        const gitStatusTxt = document.getElementById("gitStatusText");
        if (gitStatusTxt && data.git_info) {
            const credBadge = data.git_info.has_credentials ? '<span style="color:#4ade80; font-weight: 500;">(เชื่อมต่อบัญชีแล้ว ✓)</span>' : '';
            if (data.git_info.has_remote) {
                const statusColor = data.git_info.last_git_status && data.git_info.last_git_status.includes("ไม่สำเร็จ") ? "#f87171" : "#94a3b8";
                gitStatusTxt.innerHTML = `🐙 Remote: <code>${data.git_info.remote_url}</code> ${credBadge}<br><span style="color:${statusColor}; display:inline-block; margin-top:3px;">⚡ สถานะ: ${data.git_info.last_git_status || 'พร้อมใช้งาน'}</span>`;
            } else {
                gitStatusTxt.innerHTML = `🐙 Git ในเครื่องพร้อมแล้ว ${credBadge} (ใส่ GitHub Remote URL เพื่อเปิด Auto-Push อัตโนมัติ)`;
            }
        }
        handleProviderChange();
    } catch (e) {
        console.error("Failed to load settings:", e);
    }
}

function handleProviderChange() {
    const provider = document.getElementById("settingProvider").value;
    const apiKeyGroup = document.getElementById("apiKeyGroup");
    const modelGroup = document.getElementById("modelGroup");
    const baseUrlGroup = document.getElementById("baseUrlGroup");
    const helperText = document.getElementById("apiKeyHelperText");

    if (provider === "mock") {
        apiKeyGroup.style.display = "none";
        modelGroup.style.display = "none";
        baseUrlGroup.style.display = "none";
    } else if (provider === "gemini") {
        apiKeyGroup.style.display = "flex";
        modelGroup.style.display = "flex";
        baseUrlGroup.style.display = "none";
        if (document.getElementById("settingModel").value.includes("gpt") || document.getElementById("settingModel").value.includes("claude")) {
            document.getElementById("settingModel").value = "gemini-3.8-flash";
        }
        if (helperText) helperText.innerHTML = 'สมัครขอ Google Gemini API Key ได้ฟรีที่: <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer">Google AI Studio</a>';
    } else if (provider === "openai") {
        apiKeyGroup.style.display = "flex";
        modelGroup.style.display = "flex";
        baseUrlGroup.style.display = "flex";
        const currentModel = document.getElementById("settingModel").value;
        if (!currentModel || currentModel.includes("gemini") || currentModel.includes("claude") || currentModel.includes("qwen") || currentModel.includes("moonshot") || currentModel.includes("llama-3.3") || currentModel.includes("deepseek-r1-distill-llama")) {
            document.getElementById("settingModel").value = "llama-3.1-8b-instant";
        }
        const currentUrl = document.getElementById("settingBaseUrl").value;
        if (!currentUrl || currentUrl.includes("api.openai.com")) {
            document.getElementById("settingBaseUrl").value = "https://api.groq.com/openai/v1";
        }
        if (helperText) helperText.innerHTML = 'รับ Groq API Key ฟรีที่: <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer">Groq Console</a> หรือ <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer">OpenAI Platform</a>';
    } else if (provider === "claude") {
        apiKeyGroup.style.display = "flex";
        modelGroup.style.display = "flex";
        baseUrlGroup.style.display = "none";
        const currentModel = document.getElementById("settingModel").value;
        if (!currentModel || !currentModel.startsWith("claude")) {
            document.getElementById("settingModel").value = "claude-sonnet-4-5";
        }
        if (helperText) helperText.innerHTML = 'รับ Claude API Key ได้ที่: <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer">Anthropic Console</a> (ต้องเติมเครดิตก่อนใช้งาน)';
    }
}

function openSettingsModal() {
    settingsModal.classList.add("active");
}

function closeSettingsModal() {
    settingsModal.classList.remove("active");
}

function toggleApiKeyVisibility() {
    const input = document.getElementById("settingApiKey");
    const icon = document.querySelector("#toggleKeyVisibility i");
    if (input.type === "password") {
        input.type = "text";
        icon.className = "fa-solid fa-eye-slash";
    } else {
        input.type = "password";
        icon.className = "fa-solid fa-eye";
    }
}

function togglePollinationsKeyVisibility() {
    const input = document.getElementById("settingPollinationsKey");
    const icon = document.querySelector("#togglePollinationsKeyVisibility i");
    if (!input) return;
    if (input.type === "password") {
        input.type = "text";
        if (icon) icon.className = "fa-solid fa-eye-slash";
    } else {
        input.type = "password";
        if (icon) icon.className = "fa-solid fa-eye";
    }
}

async function saveSettings() {
    const provider = document.getElementById("settingProvider").value;
    const apiKey = document.getElementById("settingApiKey").value.trim();
    const model = document.getElementById("settingModel").value.trim();
    const baseUrl = document.getElementById("settingBaseUrl").value.trim();
    const persona = document.getElementById("settingPersona").value.trim();
    const polKeyInput = document.getElementById("settingPollinationsKey");
    const polKey = polKeyInput ? polKeyInput.value.trim() : "";

    const payload = {
        api_provider: provider,
        model_name: model,
        openai_base_url: baseUrl,
        custom_persona: persona
    };
    if (apiKey) payload.api_key = apiKey;
    if (polKey) payload.pollinations_api_key = polKey;

    const obsEnabledInput = document.getElementById("settingObsidianEnabled");
    if (obsEnabledInput) payload.obsidian_sync_enabled = obsEnabledInput.checked;
    const obsPathInput = document.getElementById("settingObsidianPath");
    if (obsPathInput) payload.obsidian_vault_path = obsPathInput.value.trim();

    const ghEnabledInput = document.getElementById("settingGithubEnabled");
    if (ghEnabledInput) payload.github_sync_enabled = ghEnabledInput.checked;
    const ghUrlInput = document.getElementById("settingGithubRemoteUrl");
    if (ghUrlInput) payload.github_remote_url = ghUrlInput.value.trim();

    try {
        await fetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        alert("บันทึกการตั้งค่าเรียบร้อยแล้ว");
        closeSettingsModal();
        fetchSettings();
    } catch (e) {
        alert("เกิดข้อผิดพลาดในการบันทึกการตั้งค่า");
    }
}

async function syncObsidianNow() {
    const btn = document.getElementById("btnSyncObsidianNow");
    if (!btn) return;
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> ซิงค์...';
    try {
        const res = await fetch("/api/obsidian/sync-now", { method: "POST" });
        const result = await res.json();
        if (result.status === "success") {
            alert(`✅ ซิงค์สำเร็จ!\n• บันทึกข้อมูลลง: ${result.vault_path}\n• จำนวนความจำที่ซิงค์: ${result.synced_memories} รายการ`);
            fetchSettings();
        } else {
            alert("⚠️ ไม่สามารถเข้าถึงโฟลเดอร์ Obsidian ได้ กรุณาตรวจสอบตำแหน่งที่ระบุ");
        }
    } catch (err) {
        alert("เกิดข้อผิดพลาดในการซิงค์: " + err.message);
    } finally {
        btn.innerHTML = originalHtml;
    }
}

async function pushGithubNow() {
    const btn = document.getElementById("btnGitPushNow");
    if (!btn) return;
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Push...';
    try {
        const res = await fetch("/api/obsidian/git-push", { method: "POST" });
        const result = await res.json();
        if (result.status === "success") {
            alert(`✅ อัปเดตขึ้น GitHub สำเร็จ!\n• ${result.message}`);
        } else {
            alert(`ℹ️ สถานะ Git: ${result.message}\n(หากยังไม่ได้เชื่อม Remote กรุณาใส่ URL ของ GitHub Repository แล้วบันทึกการตั้งค่า)`);
        }
        fetchSettings();
    } catch (err) {
        alert("เกิดข้อผิดพลาดในการ Push: " + err.message);
    } finally {
        btn.innerHTML = originalHtml;
    }
}
