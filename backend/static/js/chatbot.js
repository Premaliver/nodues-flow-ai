/**
 * Smart NoDues AI — Futuristic Ultra-Modern AI Chatbot ("Arya") Controller
 * Self-initializing, zero-dependency, Web Audio API sound synthesis & Voice Recognition.
 */

(function () {
    'use strict';

    // Prevent multiple initializations
    if (window.NoDuesAIChatbotLoaded) return;
    window.NoDuesAIChatbotLoaded = true;

    // Configuration & State
    const CONFIG = {
        apiEndpoint: '/api/chatbot',
        botName: 'Arya',
        botRole: 'Neural AI Assistant',
        storageKey: 'nodues_ai_chat_history_v1',
        soundKey: 'nodues_ai_chat_sound_enabled',
    };

    let isOpen = false;
    let isSoundEnabled = localStorage.getItem(CONFIG.soundKey) !== 'false';
    let isListening = false;
    let recognition = null;
    let chatHistory = [];

    // Web Audio Synthesizer for futuristic zero-asset sound chimes
    const SoundEngine = {
        ctx: null,
        init() {
            try {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (AudioCtx) this.ctx = new AudioCtx();
            } catch (e) {
                console.warn('Web Audio not supported:', e);
            }
        },
        playOpen() {
            if (!isSoundEnabled || !this.ctx) return;
            try {
                if (this.ctx.state === 'suspended') this.ctx.resume();
                const now = this.ctx.currentTime;
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(520, now);
                osc.frequency.exponentialRampToValueAtTime(880, now + 0.15);
                gain.gain.setValueAtTime(0.08, now);
                gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
                osc.connect(gain);
                gain.connect(this.ctx.destination);
                osc.start(now);
                osc.stop(now + 0.2);
            } catch(e) {}
        },
        playChime() {
            if (!isSoundEnabled || !this.ctx) return;
            try {
                if (this.ctx.state === 'suspended') this.ctx.resume();
                const now = this.ctx.currentTime;
                
                // Note 1
                const osc1 = this.ctx.createOscillator();
                const gain1 = this.ctx.createGain();
                osc1.type = 'sine';
                osc1.frequency.setValueAtTime(587.33, now); // D5
                gain1.gain.setValueAtTime(0.06, now);
                gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
                osc1.connect(gain1);
                gain1.connect(this.ctx.destination);
                osc1.start(now);
                osc1.stop(now + 0.3);

                // Note 2
                const osc2 = this.ctx.createOscillator();
                const gain2 = this.ctx.createGain();
                osc2.type = 'sine';
                osc2.frequency.setValueAtTime(880, now + 0.08); // A5
                gain2.gain.setValueAtTime(0.08, now + 0.08);
                gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.38);
                osc2.connect(gain2);
                gain2.connect(this.ctx.destination);
                osc2.start(now + 0.08);
                osc2.stop(now + 0.38);
            } catch(e) {}
        }
    };

    // Inject Widget HTML Structure
    function injectChatbotDOM() {
        if (document.getElementById('aiChatbotContainer')) return;

        // Ensure CSS is loaded
        if (!document.querySelector('link[href*="chatbot.css"]')) {
            const cssLink = document.createElement('link');
            cssLink.rel = 'stylesheet';
            cssLink.href = '/static/css/chatbot.css';
            document.head.appendChild(cssLink);
        }

        const container = document.createElement('div');
        container.id = 'aiChatbotContainer';
        container.innerHTML = `
            <!-- Floating Launcher Trigger Orb -->
            <div class="ai-chatbot-launcher" id="aiChatLauncher" title="Open AI Assistant">
                <div class="ai-launcher-tooltip" id="aiLauncherTooltip">
                    <span class="sparkle">✨</span> Need help with No-Dues? <strong>Ask AI</strong>
                </div>
                <div class="ai-launcher-orb">
                    <svg class="ai-launcher-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2 2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/>
                        <path d="M4 11v2a8 8 0 0 0 16 0v-2"/>
                        <rect x="2" y="9" width="20" height="8" rx="4"/>
                        <circle cx="8" cy="13" r="1.5" fill="currentColor"/>
                        <circle cx="16" cy="13" r="1.5" fill="currentColor"/>
                    </svg>
                    <div class="ai-launcher-badge"></div>
                </div>
            </div>

            <!-- Ultra-Modern Glassmorphic Chat Window -->
            <div class="ai-chat-window" id="aiChatWindow">
                <!-- Header -->
                <div class="ai-chat-header">
                    <div class="ai-header-profile">
                        <div class="ai-avatar-wrap">
                            <div class="ai-avatar">🤖</div>
                            <div class="ai-status-dot"></div>
                        </div>
                        <div class="ai-header-info">
                            <h4>${CONFIG.botName} <span style="font-size:0.65rem; background:rgba(255,255,255,0.25); padding:1px 6px; border-radius:10px;">AI</span></h4>
                            <p>Online • Institutional Assistant</p>
                        </div>
                    </div>
                    <div class="ai-header-actions">
                        <button type="button" class="ai-btn-icon" id="aiSoundToggleBtn" title="Toggle Sound">
                            ${isSoundEnabled ? '🔊' : '🔇'}
                        </button>
                        <button type="button" class="ai-btn-icon" id="aiClearHistoryBtn" title="Clear Chat">
                            🗑️
                        </button>
                        <button type="button" class="ai-btn-icon" id="aiCloseChatBtn" title="Close">
                            ✕
                        </button>
                    </div>
                </div>

                <!-- Chat Body -->
                <div class="ai-chat-body" id="aiChatBody"></div>

                <!-- Suggested Chips -->
                <div class="ai-suggestions-row" id="aiSuggestionsRow">
                    <div class="ai-chip" data-msg="How to apply for No-Dues?">🚀 How to apply?</div>
                    <div class="ai-chip" data-msg="What documents are compulsory?">📄 Compulsory receipts?</div>
                    <div class="ai-chip" data-msg="How to download Admit Card?">🎓 Download Admit Card</div>
                    <div class="ai-chip" data-msg="How to reset password?">🔑 Reset Password</div>
                </div>

                <!-- Input Footer -->
                <form class="ai-chat-footer" id="aiChatForm">
                    <div class="ai-input-wrap">
                        <input type="text" class="ai-input" id="aiChatInput" placeholder="Ask anything about No-Dues..." autocomplete="off">
                        <button type="button" class="ai-mic-btn" id="aiMicBtn" title="Voice Input (Speech-to-Text)">
                            🎙️
                        </button>
                    </div>
                    <button type="submit" class="ai-send-btn" id="aiSendBtn" title="Send message">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13"></line>
                            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                    </button>
                </form>
            </div>
        `;

        document.body.appendChild(container);
        SoundEngine.init();
        bindEvents();
        loadHistory();
    }

    // Markdown Parser helper
    function parseMarkdown(text) {
        if (!text) return '';
        let html = text
            // Escape special HTML chars
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // Bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Code
            .replace(/`([^`]+)`/g, '<code style="background:rgba(99,102,241,0.12); color:#4f46e5; padding:2px 6px; border-radius:4px; font-family:monospace;">$1</code>')
            // Markdown Links: [text](url)
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            // Bullet points
            .replace(/^[•\-\*]\s+(.*)$/gm, '<li style="margin-left:14px;">$1</li>')
            // Newlines
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n/g, '<br>');

        return html;
    }

    // Add message to UI
    function appendMessage(sender, text, timestamp) {
        const chatBody = document.getElementById('aiChatBody');
        if (!chatBody) return;

        const timeStr = timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const row = document.createElement('div');
        row.className = `ai-msg-row ${sender}`;

        if (sender === 'bot') {
            row.innerHTML = `
                <div class="ai-avatar" style="width:28px; height:28px; font-size:0.9rem; border-radius:8px; flex-shrink:0;">🤖</div>
                <div class="ai-msg-bubble">
                    ${parseMarkdown(text)}
                    <div class="ai-msg-time">${timeStr}</div>
                </div>
            `;
        } else {
            row.innerHTML = `
                <div class="ai-msg-bubble">
                    ${parseMarkdown(text)}
                    <div class="ai-msg-time" style="color:rgba(255,255,255,0.7);">${timeStr}</div>
                </div>
            `;
        }

        chatBody.appendChild(row);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    // Show / Hide Typing Indicator
    function showTyping() {
        const chatBody = document.getElementById('aiChatBody');
        const existing = document.getElementById('aiTypingIndicator');
        if (existing) existing.remove();

        const indicator = document.createElement('div');
        indicator.id = 'aiTypingIndicator';
        indicator.className = 'ai-msg-row bot';
        indicator.innerHTML = `
            <div class="ai-avatar" style="width:28px; height:28px; font-size:0.9rem; border-radius:8px; flex-shrink:0;">🤖</div>
            <div class="ai-typing-indicator">
                <div class="ai-typing-dot"></div>
                <div class="ai-typing-dot"></div>
                <div class="ai-typing-dot"></div>
            </div>
        `;
        chatBody.appendChild(indicator);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function hideTyping() {
        const indicator = document.getElementById('aiTypingIndicator');
        if (indicator) indicator.remove();
    }

    // Update Quick Suggestions Row
    function updateSuggestions(suggestions) {
        const row = document.getElementById('aiSuggestionsRow');
        if (!row || !suggestions || !suggestions.length) return;
        row.innerHTML = '';
        suggestions.forEach(s => {
            const chip = document.createElement('div');
            chip.className = 'ai-chip';
            chip.setAttribute('data-msg', s);
            chip.textContent = s;
            chip.onclick = () => sendMessage(s);
            row.appendChild(chip);
        });
    }

    // Send Message Handler
    async function sendMessage(userText) {
        const input = document.getElementById('aiChatInput');
        const text = (userText || (input ? input.value : '')).trim();
        if (!text) return;

        if (input) input.value = '';

        // Add user message to UI & History
        appendMessage('user', text);
        chatHistory.push({ sender: 'user', text: text, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
        saveHistory();

        showTyping();

        try {
            const res = await fetch(CONFIG.apiEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            const data = await res.json();
            hideTyping();

            if (data.success && data.reply) {
                appendMessage('bot', data.reply);
                SoundEngine.playChime();
                chatHistory.push({ sender: 'bot', text: data.reply, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
                saveHistory();

                if (data.suggestions) {
                    updateSuggestions(data.suggestions);
                }
            } else {
                appendMessage('bot', '⚠️ Sorry, I could not process that request. Please try again.');
            }
        } catch (err) {
            hideTyping();
            appendMessage('bot', '⚠️ Network connection issue. Please check your connection and try again.');
        }
    }

    // Local Storage Management
    function saveHistory() {
        try {
            localStorage.setItem(CONFIG.storageKey, JSON.stringify(chatHistory.slice(-20)));
        } catch(e) {}
    }

    function loadHistory() {
        try {
            const saved = localStorage.getItem(CONFIG.storageKey);
            if (saved) {
                chatHistory = JSON.parse(saved);
                chatHistory.forEach(m => appendMessage(m.sender, m.text, m.time));
            } else {
                // Initial Welcome Greeting
                const welcome = `👋 Hello! I am **${CONFIG.botName}** — your Smart NoDues AI Assistant.\n\nI can help you with your clearance workflow, compulsory fee receipts, admit cards, or password resets. Tap a quick question below to get started!`;
                appendMessage('bot', welcome);
                chatHistory.push({ sender: 'bot', text: welcome, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) });
                saveHistory();
            }
        } catch(e) {
            console.error('History load error:', e);
        }
    }

    function clearHistory() {
        if (confirm('Clear entire conversation history?')) {
            chatHistory = [];
            localStorage.removeItem(CONFIG.storageKey);
            const chatBody = document.getElementById('aiChatBody');
            if (chatBody) chatBody.innerHTML = '';
            loadHistory();
        }
    }

    // Speech-to-Text Voice Recognition
    function setupVoiceRecognition() {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        const micBtn = document.getElementById('aiMicBtn');
        if (!SpeechRec || !micBtn) return;

        recognition = new SpeechRec();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-IN'; // Supports Hinglish/Indian English

        recognition.onstart = () => {
            isListening = true;
            micBtn.classList.add('listening');
            micBtn.title = 'Listening... Speak now';
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            const input = document.getElementById('aiChatInput');
            if (input) {
                input.value = transcript;
                sendMessage(transcript);
            }
        };

        recognition.onerror = (event) => {
            console.warn('Speech error:', event.error);
            isListening = false;
            micBtn.classList.remove('listening');
        };

        recognition.onend = () => {
            isListening = false;
            micBtn.classList.remove('listening');
            micBtn.title = 'Voice Input (Speech-to-Text)';
        };

        micBtn.onclick = () => {
            if (isListening) {
                recognition.stop();
            } else {
                try { recognition.start(); }
                catch(e) { console.warn('Could not start speech recognition:', e); }
            }
        };
    }

    // Window Toggle & Event Bindings
    function toggleChat(open) {
        isOpen = open !== undefined ? open : !isOpen;
        const win = document.getElementById('aiChatWindow');
        const tooltip = document.getElementById('aiLauncherTooltip');
        if (!win) return;

        if (isOpen) {
            win.classList.add('active');
            if (tooltip) tooltip.style.display = 'none';
            SoundEngine.playOpen();
            const input = document.getElementById('aiChatInput');
            if (input) setTimeout(() => input.focus(), 300);
        } else {
            win.classList.remove('active');
        }
    }

    function bindEvents() {
        const launcher = document.getElementById('aiChatLauncher');
        const closeBtn = document.getElementById('aiCloseChatBtn');
        const clearBtn = document.getElementById('aiClearHistoryBtn');
        const soundBtn = document.getElementById('aiSoundToggleBtn');
        const form = document.getElementById('aiChatForm');

        if (launcher) launcher.onclick = () => toggleChat();
        if (closeBtn) closeBtn.onclick = (e) => { e.stopPropagation(); toggleChat(false); };
        if (clearBtn) clearBtn.onclick = (e) => { e.stopPropagation(); clearHistory(); };

        if (soundBtn) {
            soundBtn.onclick = (e) => {
                e.stopPropagation();
                isSoundEnabled = !isSoundEnabled;
                localStorage.setItem(CONFIG.soundKey, isSoundEnabled ? 'true' : 'false');
                soundBtn.textContent = isSoundEnabled ? '🔊' : '🔇';
                if (isSoundEnabled) SoundEngine.playChime();
            };
        }

        if (form) {
            form.onsubmit = (e) => {
                e.preventDefault();
                sendMessage();
            };
        }

        // Suggested Chips
        document.querySelectorAll('#aiSuggestionsRow .ai-chip').forEach(chip => {
            chip.onclick = () => {
                const msg = chip.getAttribute('data-msg');
                if (msg) sendMessage(msg);
            };
        });

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isOpen) {
                toggleChat(false);
            }
        });

        // Initialize Speech Recognition
        setupVoiceRecognition();
    }

    // Auto Mount on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectChatbotDOM);
    } else {
        injectChatbotDOM();
    }
})();
