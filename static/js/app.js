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

// ==================== Attachment System DOM Elements & State ====================
const attachImageBtn = document.getElementById("attachImageBtn");
const attachFolderBtn = document.getElementById("attachFolderBtn");
const imageFileInput = document.getElementById("imageFileInput");
const folderFileInput = document.getElementById("folderFileInput");
const docFileInput = document.getElementById("docFileInput");
const attachmentTray = document.getElementById("attachmentTray");
const trayItemsContainer = document.getElementById("trayItemsContainer");
const attachmentCountEl = document.getElementById("attachmentCount");
const clearAllAttachmentsBtn = document.getElementById("clearAllAttachmentsBtn");
const dragDropOverlay = document.getElementById("dragDropOverlay");
const chatSection = document.getElementById("chatSection");
const folderTreeModal = document.getElementById("folderTreeModal");
const folderModalTitle = document.getElementById("folderModalTitle");
const folderModalSubtitle = document.getElementById("folderModalSubtitle");
const folderModalTree = document.getElementById("folderModalTree");

let currentAttachments = {
    images: [],
    folder: null,
    files: []
};

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
    initDragAndDrop();
    window.addEventListener("paste", handlePasteEvent);
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

    // Attachment Event Listeners
    if (attachImageBtn && imageFileInput) {
        attachImageBtn.addEventListener("click", () => imageFileInput.click());
        imageFileInput.addEventListener("change", handleImageFileSelect);
    }
    if (attachFolderBtn && folderFileInput) {
        attachFolderBtn.addEventListener("click", () => folderFileInput.click());
        folderFileInput.addEventListener("change", handleFolderFileSelect);
    }
    if (clearAllAttachmentsBtn) {
        clearAllAttachmentsBtn.addEventListener("click", clearAllAttachments);
    }

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
    const apiKeyInputEl = document.getElementById("settingApiKey");
    if (apiKeyInputEl) {
        apiKeyInputEl.addEventListener("input", () => {
            const val = apiKeyInputEl.value.trim();
            const provSelect = document.getElementById("settingProvider");
            if (val.startsWith("gsk_") && provSelect.value !== "openai") {
                provSelect.value = "openai";
                handleProviderChange();
            } else if (val.startsWith("AIza") && provSelect.value !== "gemini") {
                provSelect.value = "gemini";
                handleProviderChange();
            } else if (val.startsWith("sk-ant-") && provSelect.value !== "claude") {
                provSelect.value = "claude";
                handleProviderChange();
            }
        });
    }
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
        startPingHeartbeat();
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
    };

    ws.onclose = () => {
        isConnected = false;
        clearInterval(pingHeartbeatInterval);
        connectionStatus.className = "status-indicator";
        connectionText.textContent = "การเชื่อมต่อหลุด - กำลังลองใหม่...";
        setTimeout(initWebSocket, 2500);
    };

    ws.onerror = (err) => {
        console.error("WebSocket Error:", err);
    };
}

let pingHeartbeatInterval = null;
function startPingHeartbeat() {
    clearInterval(pingHeartbeatInterval);
    pingHeartbeatInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
        }
    }, 15000);
}

// ตรวจจับเมื่อผู้ใช้สลับกลับมาที่หน้าจอมือถือ หรือเปิดหน้าจอขึ้นมาใหม่ ให้เชื่อมต่อทันที
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.log("[Mobile] Screen became active, reconnecting WebSocket...");
            initWebSocket();
        }
    }
});

window.addEventListener("online", () => {
    console.log("[Mobile] Network back online, reconnecting WebSocket...");
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        initWebSocket();
    }
});

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

// ==================== Message Rendering & Attachments ====================

function sendMessage() {
    const text = messageInput.value.trim();
    const hasImages = currentAttachments.images.length > 0;
    const hasFolder = currentAttachments.folder !== null;
    const hasFiles = currentAttachments.files.length > 0;

    if (!text && !hasImages && !hasFolder && !hasFiles) return;
    if (!isConnected) return;

    if (welcomeCard && welcomeCard.parentElement) {
        welcomeCard.style.display = "none";
    }

    // Clone current attachments to send and display
    const imagesToSend = [...currentAttachments.images];
    const folderToSend = currentAttachments.folder;
    const filesToSend = [...currentAttachments.files];

    // Render User Message Bubble
    createUserMessageElement(text, imagesToSend, folderToSend, filesToSend);
    messageInput.value = "";
    messageInput.style.height = "auto";
    clearAllAttachments();
    scrollToBottom();

    // Prepare payload
    const imagesPayload = imagesToSend.map(img => ({
        name: img.name,
        mime_type: img.mime_type,
        data: img.data
    }));

    const attachmentsPayload = [];
    if (folderToSend) {
        attachmentsPayload.push(folderToSend);
    }
    if (filesToSend.length) {
        filesToSend.forEach(f => attachmentsPayload.push(f));
    }

    // Send through WebSocket
    ws.send(JSON.stringify({
        type: "message",
        content: text,
        session_id: "default",
        images: imagesPayload,
        attachments: attachmentsPayload
    }));
}

function quickSend(text) {
    messageInput.value = text;
    sendMessage();
}

function createUserMessageElement(text, images = [], folder = null, files = []) {
    const row = document.createElement("div");
    row.className = "message-row user";

    let attachmentsHtml = "";

    // 1. Attached Images Grid
    if (images && images.length > 0) {
        attachmentsHtml += `<div class="msg-attached-images-grid">`;
        images.forEach(img => {
            attachmentsHtml += `
                <div class="msg-attached-image-card" onclick="window.openImageLightbox('${img.preview}', '${escapeHtml(img.name)}')">
                    <img src="${img.preview}" alt="${escapeHtml(img.name)}" title="คลิกเพื่อดูรูปภาพขนาดเต็ม">
                </div>
            `;
        });
        attachmentsHtml += `</div>`;
    }

    // 2. Attached Folder Card
    if (folder) {
        const treeEscaped = encodeURIComponent(folder.tree || "");
        attachmentsHtml += `
            <div class="msg-attached-folder-card">
                <i class="fa-solid fa-folder-open folder-icon-glow"></i>
                <div class="folder-details">
                    <div class="folder-title">📁 ${escapeHtml(folder.name)}</div>
                    <div class="folder-sub">${folder.fileCount} ไฟล์โค้ด • ${folder.totalSizeStr}</div>
                </div>
                <button type="button" class="view-tree-btn" onclick="window.viewFolderTreeModalFromChat('${escapeHtml(folder.name)}', '${folder.fileCount} ไฟล์ (${folder.totalSizeStr})', '${treeEscaped}')">
                    <i class="fa-solid fa-folder-tree"></i> ดูโครงสร้าง
                </button>
            </div>
        `;
    }

    // 3. Attached Single Files
    if (files && files.length > 0) {
        files.forEach(f => {
            attachmentsHtml += `
                <div class="msg-attached-folder-card" style="border-color: rgba(96, 165, 250, 0.3);">
                    <i class="fa-solid fa-file-code folder-icon-glow" style="color: #60a5fa;"></i>
                    <div class="folder-details">
                        <div class="folder-title">📄 ${escapeHtml(f.name)}</div>
                        <div class="folder-sub">${f.sizeStr}</div>
                    </div>
                </div>
            `;
        });
    }

    let messageTextHtml = "";
    if (text) {
        messageTextHtml = `<div>${escapeHtml(text)}</div>`;
    }

    row.innerHTML = `
        <div class="message-bubble">
            ${attachmentsHtml ? `<div class="msg-attachments-wrap">${attachmentsHtml}</div>` : ""}
            ${messageTextHtml}
        </div>
    `;
    messagesContainer.appendChild(row);
}

// ==================== Attachment Helpers & Management ====================

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsText(file);
    });
}

function compressImage(file, maxWidth = 1280, maxHeight = 1280, quality = 0.85) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                let { width, height } = img;
                if (width > maxWidth || height > maxHeight) {
                    if (width / height > maxWidth / maxHeight) {
                        height = Math.round((height * maxWidth) / width);
                        width = maxWidth;
                    } else {
                        width = Math.round((width * maxHeight) / height);
                        height = maxHeight;
                    }
                }
                const canvas = document.createElement("canvas");
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(img, 0, 0, width, height);
                const mime = file.type === "image/png" ? "image/png" : "image/jpeg";
                const dataUrl = canvas.toDataURL(mime, quality);
                const base64 = dataUrl.split(",")[1];
                resolve({
                    id: "img_" + Date.now() + "_" + Math.random().toString(36).substr(2, 5),
                    name: file.name,
                    mime_type: mime,
                    data: base64,
                    preview: dataUrl,
                    sizeStr: formatBytes(Math.round((dataUrl.length * 3) / 4))
                });
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

async function handleImageFileSelect(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    for (const file of files) {
        if (!file.type.startsWith("image/")) continue;
        const compressed = await compressImage(file);
        currentAttachments.images.push(compressed);
    }
    e.target.value = "";
    renderAttachmentTray();
}

async function handleFolderFileSelect(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    await processFolderFiles(files);
    e.target.value = "";
}

async function processFolderFiles(filesArray) {
    if (!filesArray.length) return;

    const firstRel = filesArray[0].webkitRelativePath || filesArray[0].name;
    const folderName = firstRel.includes("/") ? firstRel.split("/")[0] : "project";

    const IGNORED_PARTS = [
        "node_modules", ".git", ".venv", "venv", "__pycache__",
        "dist", "build", ".next", ".nuxt", ".idea", ".vscode", "coverage"
    ];
    const BINARY_EXTS = [
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".exe", ".dll",
        ".zip", ".tar", ".gz", ".7z", ".rar", ".mp3", ".mp4", ".mov",
        ".woff", ".woff2", ".ttf", ".eot", ".pyc", ".pdf", ".bin"
    ];

    const validFiles = [];
    let totalSize = 0;
    const MAX_SINGLE_FILE_SIZE = 120 * 1024;
    const MAX_TOTAL_FILES = 40;
    const MAX_TOTAL_SIZE = 2 * 1024 * 1024;

    for (const file of filesArray) {
        const relPath = file.webkitRelativePath || file.name;
        const pathLower = relPath.toLowerCase();

        const isIgnored = IGNORED_PARTS.some(p => pathLower.includes(`/${p}/`) || pathLower.startsWith(`${p}/`));
        if (isIgnored) continue;

        const isBinary = BINARY_EXTS.some(ext => pathLower.endsWith(ext));
        if (isBinary) continue;

        if (file.size > MAX_SINGLE_FILE_SIZE) continue;
        if (totalSize + file.size > MAX_TOTAL_SIZE || validFiles.length >= MAX_TOTAL_FILES) continue;

        try {
            const content = await readFileAsText(file);
            validFiles.push({
                path: relPath,
                name: file.name,
                size: file.size,
                sizeStr: formatBytes(file.size),
                content: content
            });
            totalSize += file.size;
        } catch (err) {
            console.warn("Could not read file:", relPath, err);
        }
    }

    const tree = validFiles.map(f => "├── " + f.path).join("\n");

    currentAttachments.folder = {
        type: "folder",
        name: folderName,
        fileCount: validFiles.length,
        totalSize: totalSize,
        totalSizeStr: formatBytes(totalSize),
        tree: tree,
        files: validFiles
    };

    renderAttachmentTray();
}

function renderAttachmentTray() {
    if (!attachmentTray || !trayItemsContainer) return;

    const totalCount = currentAttachments.images.length + 
                       (currentAttachments.folder ? 1 : 0) + 
                       currentAttachments.files.length;

    if (totalCount === 0) {
        attachmentTray.style.display = "none";
        trayItemsContainer.innerHTML = "";
        return;
    }

    attachmentTray.style.display = "block";
    if (attachmentCountEl) attachmentCountEl.textContent = totalCount;
    trayItemsContainer.innerHTML = "";

    // 1. Render Images
    currentAttachments.images.forEach(img => {
        const item = document.createElement("div");
        item.className = "tray-item image-item";
        item.innerHTML = `
            <img src="${img.preview}" class="tray-thumb-img" alt="${escapeHtml(img.name)}">
            <div class="tray-item-info">
                <span class="tray-item-name" title="${escapeHtml(img.name)}">${escapeHtml(img.name)}</span>
                <span class="tray-item-meta">${img.sizeStr}</span>
            </div>
            <button type="button" class="tray-item-btn remove-btn" onclick="removeAttachmentItem('image', '${img.id}')" title="ลบออก">&times;</button>
        `;
        trayItemsContainer.appendChild(item);
    });

    // 2. Render Folder
    if (currentAttachments.folder) {
        const f = currentAttachments.folder;
        const item = document.createElement("div");
        item.className = "tray-item folder-item";
        item.innerHTML = `
            <div class="tray-icon-box folder"><i class="fa-solid fa-folder-open"></i></div>
            <div class="tray-item-info">
                <span class="tray-item-name" title="${escapeHtml(f.name)}">📁 ${escapeHtml(f.name)}</span>
                <span class="tray-item-meta">${f.fileCount} ไฟล์ • ${f.totalSizeStr}</span>
            </div>
            <button type="button" class="tray-item-btn" onclick="openFolderTreeModal('${escapeHtml(f.name)}', '${f.fileCount} ไฟล์ (${f.totalSizeStr})', '${encodeURIComponent(f.tree)}')" title="ดูโครงสร้างไฟล์"><i class="fa-solid fa-list-check"></i></button>
            <button type="button" class="tray-item-btn remove-btn" onclick="removeAttachmentItem('folder')" title="ลบออก">&times;</button>
        `;
        trayItemsContainer.appendChild(item);
    }

    // 3. Render Files
    currentAttachments.files.forEach(file => {
        const item = document.createElement("div");
        item.className = "tray-item file-item";
        item.innerHTML = `
            <div class="tray-icon-box file"><i class="fa-solid fa-file-code"></i></div>
            <div class="tray-item-info">
                <span class="tray-item-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
                <span class="tray-item-meta">${file.sizeStr}</span>
            </div>
            <button type="button" class="tray-item-btn remove-btn" onclick="removeAttachmentItem('file', '${file.id}')" title="ลบออก">&times;</button>
        `;
        trayItemsContainer.appendChild(item);
    });
}

function removeAttachmentItem(type, id) {
    if (type === "image") {
        currentAttachments.images = currentAttachments.images.filter(img => img.id !== id);
    } else if (type === "folder") {
        currentAttachments.folder = null;
    } else if (type === "file") {
        currentAttachments.files = currentAttachments.files.filter(f => f.id !== id);
    }
    renderAttachmentTray();
}

function clearAllAttachments() {
    currentAttachments.images = [];
    currentAttachments.folder = null;
    currentAttachments.files = [];
    renderAttachmentTray();
}

function openFolderTreeModal(title, subtitle, encodedTree) {
    if (!folderTreeModal) return;
    const tree = decodeURIComponent(encodedTree || "");
    if (folderModalTitle) folderModalTitle.textContent = title || "โครงสร้างไฟล์";
    if (folderModalSubtitle) folderModalSubtitle.textContent = subtitle || "";
    if (folderModalTree) folderModalTree.textContent = tree || "(ไม่มีรายการไฟล์)";
    folderTreeModal.classList.add("active");
}

function closeFolderTreeModal() {
    if (folderTreeModal) folderTreeModal.classList.remove("active");
}

window.viewFolderTreeModalFromChat = function(name, subtitle, encodedTree) {
    openFolderTreeModal(name, subtitle, encodedTree);
};

// Clipboard Paste Support (Ctrl+V)
function handlePasteEvent(e) {
    const clipboardData = e.clipboardData || window.clipboardData;
    if (!clipboardData || !clipboardData.items) return;
    const items = clipboardData.items;
    for (const item of items) {
        if (item.type.indexOf("image") !== -1) {
            const file = item.getAsFile();
            if (file) {
                compressImage(file).then(compressed => {
                    currentAttachments.images.push(compressed);
                    renderAttachmentTray();
                });
            }
        }
    }
}

// Drag & Drop Support
function initDragAndDrop() {
    let dragCounter = 0;

    window.addEventListener("dragenter", (e) => {
        e.preventDefault();
        dragCounter++;
        if (dragDropOverlay) dragDropOverlay.classList.add("active");
    });

    window.addEventListener("dragleave", (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter <= 0 && dragDropOverlay) {
            dragCounter = 0;
            dragDropOverlay.classList.remove("active");
        }
    });

    window.addEventListener("dragover", (e) => {
        e.preventDefault();
    });

    window.addEventListener("drop", async (e) => {
        e.preventDefault();
        dragCounter = 0;
        if (dragDropOverlay) dragDropOverlay.classList.remove("active");

        const items = e.dataTransfer.items;
        const files = Array.from(e.dataTransfer.files || []);

        if (items && items.length) {
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.webkitGetAsEntry) {
                    const entry = item.webkitGetAsEntry();
                    if (entry && entry.isDirectory) {
                        const allFiles = await readEntryDirectory(entry);
                        await processFolderFiles(allFiles);
                        continue;
                    }
                }
            }
        }

        for (const file of files) {
            if (file.type.startsWith("image/")) {
                const compressed = await compressImage(file);
                currentAttachments.images.push(compressed);
            }
        }
        renderAttachmentTray();
    });
}

function readEntryDirectory(dirEntry) {
    return new Promise((resolve) => {
        const dirReader = dirEntry.createReader();
        const entries = [];
        const readEntries = () => {
            dirReader.readEntries(async (result) => {
                if (!result.length) {
                    const filePromises = entries.map(e => new Promise(res => e.file(res)));
                    const files = await Promise.all(filePromises);
                    resolve(files);
                } else {
                    for (const entry of result) {
                        if (entry.isFile) entries.push(entry);
                    }
                    readEntries();
                }
            });
        };
        readEntries();
    });
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
    if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
        const proceed = confirm(
            "⚠️ การเปิดไมโครโฟนบนมือถือต้องการการเชื่อมต่อแบบปลอดภัย (Secure Context)\n\n" +
            "หากไมค์ไม่ทำงาน แนะนำให้:\n" +
            "1. เปิดผ่าน HTTPS (:8443) หรือ\n" +
            "2. บน Chrome Android ให้ไปที่ chrome://flags แล้วเปิด 'Insecure origins treated as secure'\n\n" +
            "ต้องการเปิดหน้าจอ QR Code และวิธีเปิดไมค์สำหรับมือถือหรือไม่?"
        );
        if (proceed) {
            openMobileConnectModal();
            return;
        }
    }

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
        // Update API Sync card and device sharing badges
        const syncCard = document.getElementById("apiSyncCard");
        const syncTag = document.getElementById("syncStatusTag");
        const syncDesc = document.getElementById("syncStatusDesc");
        const apiKeyBadge = document.getElementById("apiKeyActiveBadge");
        const apiKeyActiveText = document.getElementById("apiKeyActiveText");

        if (data.has_api_key) {
            document.getElementById("settingApiKey").placeholder = `ใส่คีย์ใหม่เมื่อต้องการเปลี่ยน (ปัจจุบัน: ${data.masked_api_key})`;
            if (apiKeyBadge && apiKeyActiveText) {
                apiKeyBadge.style.display = "flex";
                apiKeyActiveText.innerHTML = `<strong>คีย์หลัก:</strong> ${data.masked_api_key} • บันทึกใน .env และซิงค์กับมือถือเรียบร้อย ✓`;
            }
            if (syncCard) {
                syncCard.className = "api-sync-card";
                if (syncTag) syncTag.textContent = "ใช้งานได้ทุกอุปกรณ์ ✓";
                if (syncDesc) syncDesc.innerHTML = `API Key ถูกบันทึกไว้ในระบบและไฟล์ <code>.env</code> ถาวรแล้ว • มือถือและทุกเครื่องที่เชื่อมต่อจะใช้คีย์นี้อัตโนมัติ ไม่ต้องกรอกซ้ำ`;
            }
        } else {
            document.getElementById("settingApiKey").placeholder = "ใส่ API Key เพื่อเริ่มใช้งาน";
            if (apiKeyBadge) apiKeyBadge.style.display = "none";
            if (syncCard) {
                syncCard.className = "api-sync-card warning";
                if (syncTag) syncTag.textContent = "ยังไม่ได้ระบุ Key";
                if (syncDesc) syncDesc.innerHTML = `ยังไม่มี API Key ในระบบ กรุณาใส่คีย์ด้านล่างแล้วกดบันทึก ระบบจะบันทึกถาวรและซิงค์ให้มือถือใช้ทันที`;
            }
        }

        if (data.has_pollinations_key) {
            const polInput = document.getElementById("settingPollinationsKey");
            if (polInput) polInput.placeholder = `ใส่คีย์ใหม่เมื่อต้องการเปลี่ยน (ปัจจุบัน: ${data.masked_pollinations_key})`;
            const polBadge = document.getElementById("pollinationsKeyActiveBadge");
            const polActiveText = document.getElementById("pollinationsKeyActiveText");
            if (polBadge && polActiveText) {
                polBadge.style.display = "flex";
                polActiveText.innerHTML = `<strong>Key วาดภาพ:</strong> ${data.masked_pollinations_key} • ซิงค์กับมือถือเรียบร้อย ✓`;
            }
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
        if (!currentModel || currentModel.includes("gemini") || currentModel.includes("claude") || currentModel.includes("llama-3.1") || currentModel.includes("llama-3.3") || currentModel.includes("deepseek-r1-distill-llama")) {
            document.getElementById("settingModel").value = "qwen/qwen3.8-27b";
        }
        const currentUrl = document.getElementById("settingBaseUrl").value;
        if (!currentUrl || currentUrl.includes("api.openai.com")) {
            document.getElementById("settingBaseUrl").value = "https://api.groq.com/openai/v1";
        }
        if (helperText) helperText.innerHTML = 'รับ Groq API Key ฟรีที่: <a href="https://console.groq.com/keys" target="_blank" rel="noreferrer">Groq Console</a> (แนะนำโมเดล <code>qwen/qwen3.8-27b</code> เร็วและเก่งภาษาไทย)';
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

    let finalProvider = provider;
    if (apiKey.startsWith("gsk_")) finalProvider = "openai";
    else if (apiKey.startsWith("AIza")) finalProvider = "gemini";
    else if (apiKey.startsWith("sk-ant-")) finalProvider = "claude";

    const payload = {
        api_provider: finalProvider,
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

// ========================================================
// Video Editing Studio (CapCut PC & Adobe Premiere Pro)
// ========================================================

const videoStudioModal = document.getElementById("videoStudioModal");
let studioScenes = [
    {
        title: "Hook (ดึงดูดสายตา)",
        duration: 3.5,
        text: "สวัสดีครับทุกคน วันนี้ Friday มีทริคเด็ดๆ มาแชร์กันครับ!",
        visual_idea: "ภาพเปิดมุมมองกว้าง Zoom เข้าเร็วๆ สไตล์ Viral Short"
    },
    {
        title: "Main Content (จุดสำคัญ)",
        duration: 4.5,
        text: "เทคนิคง่ายๆ ที่ทำให้การทำงานเร็วขึ้นถึง 10 เท่า",
        visual_idea: "โคลสอัปขั้นตอนทำทีละสเต็ป พร้อมไฮไลท์ตัวหนังสือ"
    },
    {
        title: "Call To Action (ปิดท้าย)",
        duration: 3.5,
        text: "อย่าลืมกดติดตามและกดหัวใจเพื่อไม่พลาดคลิปถัดไปนะครับ!",
        visual_idea: "ปุ่ม Follow ดุ๊กดิ๊ก และลูกศรชี้โปรไฟล์"
    }
];

let cachedVideoStatus = null;
let cachedLocalProjects = { capcut_drafts: [], premiere_projects: [] };

function openVideoStudioModal() {
    if (videoStudioModal) {
        videoStudioModal.classList.add("active");
        renderStudioScenes();
        loadVideoStatusAndDrafts();
    }
}

function closeVideoStudioModal() {
    if (videoStudioModal) {
        videoStudioModal.classList.remove("active");
    }
}

function switchVideoTab(tabName) {
    document.querySelectorAll(".video-tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tabName);
    });
    document.querySelectorAll(".video-tab-content").forEach(content => {
        content.classList.toggle("active", content.id === `tabContent_${tabName}`);
    });
    if (tabName === "local") {
        loadVideoStatusAndDrafts();
    }
}

async function loadVideoStatusAndDrafts() {
    try {
        const [statusRes, draftsRes] = await Promise.all([
            fetch("/api/video/status"),
            fetch("/api/video/drafts")
        ]);
        const statusData = await statusRes.json();
        const draftsData = await draftsRes.json();

        cachedVideoStatus = statusData;
        cachedLocalProjects = draftsData;

        // อัปเดตสถานะ CapCut
        const capcutStatusText = document.getElementById("capcutStatusText");
        if (capcutStatusText && statusData.environment && statusData.environment.capcut) {
            const cc = statusData.environment.capcut;
            if (cc.direct_sync_supported) {
                capcutStatusText.innerHTML = `<span style="color:#22d3ee">พร้อมซิงค์ (${statusData.capcut_draft_count} โปรเจกต์)</span>`;
            } else if (cc.installed) {
                capcutStatusText.innerHTML = `<span style="color:#22d3ee">ติดตั้งแล้ว</span>`;
            } else {
                capcutStatusText.innerHTML = `<span style="color:#94a3b8">ไม่พบในเครื่อง</span>`;
            }
        }

        // อัปเดตสถานะ Premiere Pro
        const premiereStatusText = document.getElementById("premiereStatusText");
        if (premiereStatusText && statusData.environment && statusData.environment.premiere) {
            const pr = statusData.environment.premiere;
            if (pr.installed) {
                premiereStatusText.innerHTML = `<span style="color:#c084fc">พร้อมใช้งาน (XML / JSX / SRT)</span>`;
            } else {
                premiereStatusText.innerHTML = `<span style="color:#38bdf8">พร้อมส่งออกไฟล์ XML / JSX</span>`;
            }
        }

        // อัปเดตสถานะ Alight Motion
        const alightStatusText = document.getElementById("alightStatusText");
        if (alightStatusText) {
            const amCount = statusData.alightmotion_count || (draftsData.alightmotion_projects ? draftsData.alightmotion_projects.length : 0);
            alightStatusText.innerHTML = `<span style="color:#fbbf24">พร้อมส่งออก XML (${amCount} โปรเจกต์)</span>`;
        }

        // อัปเดตจำนวนโปรเจกต์ทั้งหมด
        const localProjectsCount = document.getElementById("localProjectsCount");
        if (localProjectsCount) {
            const totalCount = (draftsData.capcut_drafts?.length || 0) + 
                               (draftsData.premiere_projects?.length || 0) + 
                               (draftsData.alightmotion_projects?.length || 0);
            localProjectsCount.textContent = totalCount;
        }

        renderLocalProjectsList();
    } catch (e) {
        console.error("Error loading video status:", e);
    }
}

function renderStudioScenes() {
    const container = document.getElementById("studioScenesList");
    const durBadge = document.getElementById("totalDurationBadge");
    if (!container) return;

    let totalDur = 0;
    container.innerHTML = "";

    studioScenes.forEach((scene, idx) => {
        const dur = parseFloat(scene.duration) || 3.0;
        totalDur += dur;

        const card = document.createElement("div");
        card.className = "scene-card-item";
        card.innerHTML = `
            <div class="scene-card-top">
                <div class="scene-number-title">
                    <span class="scene-num-badge">${idx + 1}</span>
                    <input type="text" class="scene-title-input" value="${escapeHtml(scene.title || `ฉากที่ ${idx+1}`)}" onchange="updateSceneField(${idx}, 'title', this.value)">
                </div>
                <div class="scene-controls">
                    <div class="scene-dur-wrap">
                        <i class="fa-solid fa-clock"></i>
                        <input type="number" step="0.5" min="1" max="120" class="scene-dur-input" value="${dur}" onchange="updateSceneField(${idx}, 'duration', parseFloat(this.value))"> วินาที
                    </div>
                    <button type="button" class="scene-btn-icon listen-btn" title="ฟังเสียงพากย์ฉากนี้" onclick="previewSceneTts(${idx})">
                        <i class="fa-solid fa-volume-high"></i>
                    </button>
                    <button type="button" class="scene-btn-icon" title="ลบฉากนี้" onclick="deleteScene(${idx})">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            </div>
            <textarea class="scene-text-input" placeholder="สคริปต์เสียงพากย์และซับไตเติลของฉากนี้..." onchange="updateSceneField(${idx}, 'text', this.value)">${escapeHtml(scene.text || '')}</textarea>
            <input type="text" class="scene-visual-input" placeholder="💡 คำแนะนำภาพ/B-Roll (เช่น ภาพมือถือ, กล่องพัสดุ, เอฟเฟกต์ซูม)..." value="${escapeHtml(scene.visual_idea || '')}" onchange="updateSceneField(${idx}, 'visual_idea', this.value)">
        `;
        container.appendChild(card);
    });

    if (durBadge) {
        durBadge.textContent = `ความยาวรวม: ~${totalDur.toFixed(1)} วินาที`;
    }
}

function updateSceneField(idx, field, value) {
    if (studioScenes[idx]) {
        studioScenes[idx][field] = value;
        if (field === "duration") {
            const durBadge = document.getElementById("totalDurationBadge");
            const totalDur = studioScenes.reduce((sum, s) => sum + (parseFloat(s.duration) || 0), 0);
            if (durBadge) durBadge.textContent = `ความยาวรวม: ~${totalDur.toFixed(1)} วินาที`;
        }
    }
}

function addNewScene() {
    studioScenes.push({
        title: `ฉากที่ ${studioScenes.length + 1}`,
        duration: 4.0,
        text: "พิมพ์ข้อความเสียงพากย์ของฉากนี้...",
        visual_idea: "ภาพประกอบที่สอดคล้องกับเนื้อหา"
    });
    renderStudioScenes();
}

function deleteScene(idx) {
    if (studioScenes.length <= 1) {
        alert("ต้องมีอย่างน้อย 1 ฉากในโปรเจกต์ค่ะ");
        return;
    }
    studioScenes.splice(idx, 1);
    renderStudioScenes();
}

async function previewSceneTts(idx) {
    const scene = studioScenes[idx];
    if (!scene || !scene.text.trim()) {
        alert("กรุณาใส่ข้อความสคริปต์ก่อนทดลองฟังเสียงค่ะ");
        return;
    }
    playAudioMessage(scene.text);
}

async function generateAiStoryboard() {
    const promptInput = document.getElementById("studioTopicPrompt");
    const prompt = promptInput?.value.trim();
    if (!prompt) {
        alert("กรุณาพิมพ์หัวข้อหรือไอเดียคลิปก่อนนะคะ");
        return;
    }

    const btn = document.getElementById("btnStudioAiPlan");
    const origHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> กำลังคิด...';
    btn.disabled = true;

    try {
        const aspect = document.getElementById("studioAspectRatio")?.value || "9:16";
        const res = await fetch("/api/video/plan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: prompt, aspect_ratio: aspect })
        });
        const data = await res.json();
        if (data.scenes && data.scenes.length > 0) {
            studioScenes = data.scenes;
            const nameInput = document.getElementById("studioProjectName");
            if (nameInput && data.title) {
                nameInput.value = data.title.replace(/\s+/g, '_');
            }
            renderStudioScenes();
        }
    } catch (e) {
        alert("เกิดข้อผิดพลาดในการวางโครงเรื่อง: " + e.message);
    } finally {
        btn.innerHTML = origHtml;
        btn.disabled = false;
    }
}

async function executeExportProject(platform) {
    const projectName = document.getElementById("studioProjectName")?.value.trim() || `Friday_${Date.now()}`;
    const aspect = document.getElementById("studioAspectRatio")?.value || "9:16";
    const voice = document.getElementById("studioVoiceSelect")?.value || "th-TH-PremwadeeNeural";

    const btnCapCut = document.getElementById("btnBuildCapCut");
    const btnPrem = document.getElementById("btnBuildPremiere");
    const btnAlight = document.getElementById("btnBuildAlight");
    const btnBoth = document.getElementById("btnBuildBoth");

    const loadingText = '<i class="fa-solid fa-spinner fa-spin"></i> กำลังประมวลผล...';
    if (platform === "capcut" && btnCapCut) btnCapCut.innerHTML = loadingText;
    if (platform === "premiere" && btnPrem) btnPrem.innerHTML = loadingText;
    if (platform === "alightmotion" && btnAlight) btnAlight.innerHTML = loadingText;
    if ((platform === "both" || platform === "all") && btnBoth) btnBoth.innerHTML = loadingText;

    try {
        const payload = {
            platform: platform,
            project_name: projectName,
            aspect_ratio: aspect,
            scenes: studioScenes,
            generate_voiceover: true,
            voice: voice
        };

        const res = await fetch("/api/video/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.status === "success") {
            let msg = `🎉 สร้างโปรเจกต์ "${projectName}" สำเร็จเรียบร้อยแล้วค่ะ!\n\n`;
            if (result.results?.capcut?.status === "success") {
                msg += `✂️ CapCut PC:\n- บันทึกลง Drafts ในเครื่องแล้ว\n- ที่อยู่: ${result.results.capcut.project_folder}\n- เปิดแอป CapCut จะพบโปรเจกต์นี้ทันที!\n\n`;
            }
            if (result.results?.premiere?.status === "success") {
                msg += `🎞️ Adobe Premiere Pro:\n- สร้างไฟล์ .xml, .jsx, .srt เรียบร้อย\n- ที่อยู่: ${result.results.premiere.export_folder}\n- นำเข้า .xml เข้า Premiere Pro ได้ทันที!\n\n`;
            }
            if (result.results?.alightmotion?.status === "success") {
                msg += `📱 Alight Motion:\n- สร้างไฟล์ XML Package เรียบร้อย\n- ที่อยู่: ${result.results.alightmotion.project_folder}\n- สามารถกดดาวน์โหลดไฟล์ .xml ได้จากแท็บ "โปรเจกต์ในเครื่อง" เพื่อแชร์เข้าแอปในมือถือได้ทันทีค่ะ!`;
            }

            alert(msg);
            loadVideoStatusAndDrafts();
        } else {
            alert("⚠️ เกิดข้อผิดพลาดในการสร้างโปรเจกต์: " + JSON.stringify(result));
        }
    } catch (e) {
        alert("เกิดข้อผิดพลาดในการเชื่อมต่อ: " + e.message);
    } finally {
        if (btnCapCut) btnCapCut.innerHTML = '<i class="fa-solid fa-scissors"></i> บันทึกลง CapCut PC ทันที';
        if (btnPrem) btnPrem.innerHTML = '<i class="fa-solid fa-film"></i> ส่งออก Premiere Pro (.xml + .jsx)';
        if (btnAlight) btnAlight.innerHTML = '<i class="fa-solid fa-play"></i> ส่งออก Alight Motion (.xml)';
        if (btnBoth) btnBoth.innerHTML = '<i class="fa-solid fa-bolt"></i> ส่งออกครบทุกแอป';
    }
}

function renderLocalProjectsList() {
    const ccContainer = document.getElementById("capcutProjectsList");
    const prContainer = document.getElementById("premiereProjectsList");
    const amContainer = document.getElementById("alightProjectsList");
    const ccCount = document.getElementById("capcutCountLabel");
    const prCount = document.getElementById("premiereCountLabel");
    const amCount = document.getElementById("alightCountLabel");

    if (ccContainer && cachedLocalProjects.capcut_drafts) {
        const drafts = cachedLocalProjects.capcut_drafts;
        if (ccCount) ccCount.textContent = drafts.length;
        if (drafts.length === 0) {
            ccContainer.innerHTML = '<div style="color:#94a3b8; font-size:0.85rem; padding:10px; text-align:center;">ไม่พบโปรเจกต์ในเครื่อง</div>';
        } else {
            ccContainer.innerHTML = drafts.map(d => `
                <div class="local-project-item">
                    <div class="item-meta">
                        <div class="item-name" title="${escapeHtml(d.name)}">✂️ ${escapeHtml(d.name)}</div>
                        <div class="item-sub">⏱️ ${d.duration_sec}s • 📅 ${d.created || 'ไม่ระบุ'}</div>
                    </div>
                    <div class="item-actions">
                        <button type="button" class="btn btn-outline btn-sm" onclick="openFolderDirect('${escapePath(d.path)}')" title="เปิดโฟลเดอร์"><i class="fa-solid fa-folder"></i></button>
                    </div>
                </div>
            `).join("");
        }
    }

    if (prContainer && cachedLocalProjects.premiere_projects) {
        const projs = cachedLocalProjects.premiere_projects;
        if (prCount) prCount.textContent = projs.length;
        if (projs.length === 0) {
            prContainer.innerHTML = '<div style="color:#94a3b8; font-size:0.85rem; padding:10px; text-align:center;">ยังไม่มีโปรเจกต์ Premiere ที่ส่งออก</div>';
        } else {
            prContainer.innerHTML = projs.map(p => `
                <div class="local-project-item">
                    <div class="item-meta">
                        <div class="item-name" title="${escapeHtml(p.name)}">🎞️ ${escapeHtml(p.name)}</div>
                        <div class="item-sub">📅 ${p.created} • XML & SRT Ready</div>
                    </div>
                    <div class="item-actions">
                        <button type="button" class="btn btn-outline btn-sm" onclick="openFolderDirect('${escapePath(p.path)}')" title="เปิดโฟลเดอร์"><i class="fa-solid fa-folder"></i></button>
                    </div>
                </div>
            `).join("");
        }
    }

    if (amContainer && cachedLocalProjects.alightmotion_projects) {
        const amProjs = cachedLocalProjects.alightmotion_projects;
        if (amCount) amCount.textContent = amProjs.length;
        if (amProjs.length === 0) {
            amContainer.innerHTML = '<div style="color:#94a3b8; font-size:0.85rem; padding:10px; text-align:center;">ยังไม่มีโปรเจกต์ Alight Motion XML</div>';
        } else {
            amContainer.innerHTML = amProjs.map(p => `
                <div class="local-project-item">
                    <div class="item-meta">
                        <div class="item-name" title="${escapeHtml(p.name)}">📱 ${escapeHtml(p.name)}</div>
                        <div class="item-sub">📅 ${p.created} • XML Package</div>
                    </div>
                    <div class="item-actions">
                        <a href="${p.download_url}" download class="btn-download-xml" title="ดาวน์โหลดไฟล์ .xml สำหรับนำเข้า Alight Motion">
                            <i class="fa-solid fa-download"></i> ดาวน์โหลด XML
                        </a>
                        <button type="button" class="btn btn-outline btn-sm" onclick="openFolderDirect('${escapePath(p.path)}')" title="เปิดโฟลเดอร์">
                            <i class="fa-solid fa-folder"></i>
                        </button>
                    </div>
                </div>
            `).join("");
        }
    }
}

function escapePath(p) {
    if (!p) return "";
    return p.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

async function openFolderDirect(targetPath) {
    try {
        await fetch("/api/video/open", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "folder", target_path: targetPath })
        });
    } catch (e) {
        console.error("Open folder error:", e);
    }
}

async function openCapCutApp() {
    try {
        const res = await fetch("/api/video/open", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "capcut" })
        });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("ไม่สามารถเปิด CapCut ได้: " + e.message);
    }
}

async function openPremiereApp() {
    try {
        const res = await fetch("/api/video/open", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "premiere" })
        });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("ไม่สามารถเปิด Premiere Pro ได้: " + e.message);
    }
}

// Window global functions for chat inline cards
window.createVideoProjectFromChat = async function(platform, planData) {
    let plan = planData;
    if (typeof planData === "string") {
        try { plan = JSON.parse(planData); } catch(e) {}
    }
    if (!plan || !plan.scenes) return;

    const projectName = (plan.title || "Friday_Project").replace(/[^a-zA-Z0-9_\u0E00-\u0E7F]/g, "_");
    const aspect = plan.aspect_ratio || "9:16";

    const platformLabel = platform === 'capcut' ? 'CapCut PC' : (platform === 'premiere' ? 'Adobe Premiere Pro' : 'Alight Motion (.xml)');
    const confirmed = confirm(`🎬 คุณต้องการสร้างโปรเจกต์ "${projectName}" สำหรับ ${platformLabel} ทันทีใช่หรือไม่?`);
    if (!confirmed) return;

    try {
        const payload = {
            platform: platform,
            project_name: projectName,
            aspect_ratio: aspect,
            scenes: plan.scenes,
            generate_voiceover: true,
            voice: "th-TH-PremwadeeNeural"
        };

        const res = await fetch("/api/video/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.status === "success") {
            if (platform === "alightmotion") {
                const downloadUrl = result.results?.alightmotion?.download_url;
                const folderPath = result.results?.alightmotion?.project_folder;
                const wantDownload = confirm(`✅ สร้างไฟล์ Alight Motion XML Package สำหรับ "${projectName}" สำเร็จเรียบร้อยแล้วค่ะ!\n\nต้องการดาวน์โหลดไฟล์ .xml ลงเครื่อง/มือถือ ทันทีเลยหรือไม่?`);
                if (wantDownload && downloadUrl) {
                    window.location.href = downloadUrl;
                } else if (folderPath) {
                    openFolderDirect(folderPath);
                }
            } else {
                const folderPath = platform === "capcut" 
                    ? result.results?.capcut?.project_folder 
                    : result.results?.premiere?.export_folder;

                const actionChoice = confirm(`✅ สร้างโปรเจกต์ ${projectName} ลงเครื่องเรียบร้อยแล้วค่ะ!\n\nต้องการเปิดโฟลเดอร์โปรเจกต์ใน Windows Explorer ทันทีหรือไม่?`);
                if (actionChoice && folderPath) {
                    openFolderDirect(folderPath);
                }
            }
        } else {
            alert("⚠️ เกิดข้อผิดพลาด: " + JSON.stringify(result));
        }
    } catch (e) {
        alert("เกิดข้อผิดพลาด: " + e.message);
    }
};

window.openVideoStudioWithPlan = function(planData) {
    let plan = planData;
    if (typeof planData === "string") {
        try { plan = JSON.parse(planData); } catch(e) {}
    }
    if (plan && plan.scenes) {
        studioScenes = plan.scenes;
        const nameInput = document.getElementById("studioProjectName");
        if (nameInput && plan.title) {
            nameInput.value = plan.title.replace(/\s+/g, '_');
        }
        const aspectSelect = document.getElementById("studioAspectRatio");
        if (aspectSelect && plan.aspect_ratio) {
            aspectSelect.value = plan.aspect_ratio;
        }
    }
    openVideoStudioModal();
};

window.openVideoStudioModal = openVideoStudioModal;
window.closeVideoStudioModal = closeVideoStudioModal;
window.switchVideoTab = switchVideoTab;
window.generateAiStoryboard = generateAiStoryboard;
window.addNewScene = addNewScene;
window.deleteScene = deleteScene;
window.updateSceneField = updateSceneField;
window.previewSceneTts = previewSceneTts;
window.executeExportProject = executeExportProject;
window.openFolderDirect = openFolderDirect;
window.openCapCutApp = openCapCutApp;
window.openPremiereApp = openPremiereApp;
window.loadVideoStatusAndDrafts = loadVideoStatusAndDrafts;

// Init Event Listeners
document.getElementById("openVideoStudioBtnHeader")?.addEventListener("click", openVideoStudioModal);
document.getElementById("openVideoStudioBtnPill")?.addEventListener("click", openVideoStudioModal);

// ==================== Mobile Audio Autoplay Unlocker ====================
let mobileAudioContext = null;
let isAudioUnlocked = false;

function unlockMobileAudio() {
    if (isAudioUnlocked) return;
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
            if (!mobileAudioContext) mobileAudioContext = new AudioCtx();
            if (mobileAudioContext.state === "suspended") mobileAudioContext.resume();
            const buffer = mobileAudioContext.createBuffer(1, 1, 22050);
            const source = mobileAudioContext.createBufferSource();
            source.buffer = buffer;
            source.connect(mobileAudioContext.destination);
            source.start(0);
        }
        const silentAudio = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA");
        silentAudio.play().then(() => silentAudio.pause()).catch(() => {});
        isAudioUnlocked = true;
        console.log("[Mobile] Audio unlocked for real-time voice playback");
    } catch (e) {
        console.warn("[Mobile] Unlock audio failed:", e);
    }
}
window.addEventListener("touchstart", unlockMobileAudio, { once: true, passive: true });
window.addEventListener("pointerdown", unlockMobileAudio, { once: true, passive: true });
window.addEventListener("click", unlockMobileAudio, { once: true, passive: true });

// ==================== Mobile Connect Modal Controller ====================
let mobileInfoCache = null;
let currentMobileProtocol = "http";

async function openMobileConnectModal() {
    const modal = document.getElementById("mobileConnectModal");
    if (!modal) return;
    modal.classList.add("active");
    
    try {
        if (!mobileInfoCache) {
            const res = await fetch("/api/mobile/info");
            mobileInfoCache = await res.json();
        }
        updateMobileModalView();
    } catch (e) {
        console.error("Fetch mobile info error:", e);
    }
}

function closeMobileConnectModal() {
    const modal = document.getElementById("mobileConnectModal");
    if (modal) modal.classList.remove("active");
}

function switchMobileProtocol(protocol) {
    currentMobileProtocol = protocol;
    const tabHttp = document.getElementById("tabMobileHttp");
    const tabHttps = document.getElementById("tabMobileHttps");
    if (tabHttp) tabHttp.classList.toggle("active", protocol === "http");
    if (tabHttps) tabHttps.classList.toggle("active", protocol === "https");
    updateMobileModalView();
}

function updateMobileModalView() {
    const input = document.getElementById("mobileUrlDisplay");
    const qrImg = document.getElementById("mobileQrImg");
    if (!mobileInfoCache) return;
    
    const targetUrl = currentMobileProtocol === "https" 
        ? mobileInfoCache.https_url 
        : mobileInfoCache.http_url;
        
    if (input) input.value = targetUrl;
    if (qrImg) qrImg.src = `/api/mobile/qr?url=${encodeURIComponent(targetUrl)}&t=${Date.now()}`;
}

function copyMobileLink() {
    const input = document.getElementById("mobileUrlDisplay");
    if (!input || !input.value) return;
    navigator.clipboard.writeText(input.value).then(() => {
        alert("📋 คัดลอกลิงก์สำหรับมือถือเรียบร้อยแล้วค่ะ:\n" + input.value);
    }).catch(() => {
        input.select();
        document.execCommand("copy");
        alert("📋 คัดลอกลิงก์เรียบร้อยแล้วค่ะ");
    });
}

window.openMobileConnectModal = openMobileConnectModal;
window.closeMobileConnectModal = closeMobileConnectModal;
window.switchMobileProtocol = switchMobileProtocol;
window.copyMobileLink = copyMobileLink;

document.getElementById("openMobileConnectBtn")?.addEventListener("click", openMobileConnectModal);


