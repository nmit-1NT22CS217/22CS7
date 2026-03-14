/**
 * PII Anonymizer Extension - Popup Script
 * Handles the main popup UI interactions
 */

// Configuration
const CONFIG = {
    // Default API URL - will be overridden by user settings
    DEFAULT_API_URL: 'http://localhost:5000',
    STORAGE_KEYS: {
        API_URL: 'pii_api_url',
        HISTORY: 'pii_history',
        SETTINGS: 'pii_settings'
    },
    MAX_HISTORY: 50
};

// State
let apiUrl = CONFIG.DEFAULT_API_URL;
let isConnected = false;

// DOM Elements
const elements = {};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', init);

async function init() {
    cacheElements();
    await loadSettings();
    setupEventListeners();
    checkConnection();
    loadHistory();
}

function cacheElements() {
    elements.statusBar = document.getElementById('statusBar');
    elements.statusDot = document.getElementById('statusDot');
    elements.statusText = document.getElementById('statusText');
    elements.inputText = document.getElementById('inputText');
    elements.charCount = document.getElementById('charCount');
    elements.callLlm = document.getElementById('callLlm');
    elements.anonymizeBtn = document.getElementById('anonymizeBtn');
    elements.pasteBtn = document.getElementById('pasteBtn');
    elements.resultGroup = document.getElementById('resultGroup');
    elements.resultBox = document.getElementById('resultBox');
    elements.llmResultGroup = document.getElementById('llmResultGroup');
    elements.llmResultBox = document.getElementById('llmResultBox');
    elements.deanonResultBox = document.getElementById('deanonResultBox');
    elements.mappingsInfo = document.getElementById('mappingsInfo');
    elements.deanonInput = document.getElementById('deanonInput');
    elements.deanonymizeBtn = document.getElementById('deanonymizeBtn');
    elements.deanonResultGroup = document.getElementById('deanonResultGroup');
    elements.deanonResult = document.getElementById('deanonResult');
    elements.historyList = document.getElementById('historyList');
    elements.clearHistoryBtn = document.getElementById('clearHistoryBtn');
    elements.toast = document.getElementById('toast');
}

async function loadSettings() {
    try {
        const result = await chrome.storage.sync.get(CONFIG.STORAGE_KEYS.API_URL);
        if (result[CONFIG.STORAGE_KEYS.API_URL]) {
            apiUrl = result[CONFIG.STORAGE_KEYS.API_URL];
        }
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

function setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Character count
    elements.inputText.addEventListener('input', () => {
        elements.charCount.textContent = elements.inputText.value.length;
    });

    // Main actions
    elements.anonymizeBtn.addEventListener('click', handleAnonymize);
    elements.pasteBtn.addEventListener('click', handlePaste);
    elements.deanonymizeBtn.addEventListener('click', handleDeanonymize);

    // Copy buttons
    document.getElementById('copyResultBtn').addEventListener('click', () => {
        copyToClipboard(elements.resultBox.textContent);
    });
    document.getElementById('copyLlmBtn').addEventListener('click', () => {
        copyToClipboard(elements.llmResultBox.textContent);
    });
    document.getElementById('copyDeanonBtn').addEventListener('click', () => {
        copyToClipboard(elements.deanonResultBox.textContent);
    });
    document.getElementById('copyDeanonResultBtn').addEventListener('click', () => {
        copyToClipboard(elements.deanonResult.textContent);
    });

    // History
    elements.clearHistoryBtn.addEventListener('click', clearHistory);
}

function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabId}-tab`);
    });
}

async function checkConnection() {
    try {
        const response = await fetch(`${apiUrl}/api/health`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const data = await response.json();
            isConnected = true;
            elements.statusDot.className = 'status-dot connected';
            elements.statusText.textContent = `Connected to API (${data.llm_mode} mode)`;
        } else {
            throw new Error('API not responding');
        }
    } catch (error) {
        isConnected = false;
        elements.statusDot.className = 'status-dot error';
        elements.statusText.textContent = 'Not connected - Check settings';
    }
}

async function handleAnonymize() {
    const text = elements.inputText.value.trim();
    if (!text) {
        showToast('Please enter some text to anonymize', 'error');
        return;
    }

    if (!isConnected) {
        showToast('Not connected to API. Check settings.', 'error');
        return;
    }

    const mode = document.querySelector('input[name="mode"]:checked').value;
    const callLlm = elements.callLlm.checked;

    elements.anonymizeBtn.disabled = true;
    elements.anonymizeBtn.classList.add('loading');

    try {
        const response = await fetch(`${apiUrl}/api/anonymize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, mode, call_llm: callLlm })
        });

        const data = await response.json();

        if (response.ok) {
            // Show results
            elements.resultBox.textContent = data.anonymized_text;
            elements.resultGroup.style.display = 'block';

            // Show mappings info
            const reversible = data.reversible ? 'reversible' : 'irreversible';
            elements.mappingsInfo.textContent = `Mode: ${mode} (${reversible}) | Entities found: ${data.mappings_count}`;

            // Handle LLM response
            if (callLlm && data.llm_response) {
                elements.llmResultBox.textContent = data.llm_response;
                elements.deanonResultBox.textContent = data.deanonymized_output || data.llm_response;
                elements.llmResultGroup.style.display = 'block';
            } else {
                elements.llmResultGroup.style.display = 'none';
            }

            // Save to history
            saveToHistory({
                original: text.substring(0, 100),
                anonymized: data.anonymized_text.substring(0, 100),
                mode,
                timestamp: Date.now()
            });

            showToast('Text anonymized successfully!', 'success');
        } else {
            throw new Error(data.error || 'Anonymization failed');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.anonymizeBtn.disabled = false;
        elements.anonymizeBtn.classList.remove('loading');
    }
}

async function handlePaste() {
    try {
        const text = await navigator.clipboard.readText();
        elements.inputText.value = text;
        elements.charCount.textContent = text.length;
        showToast('Pasted from clipboard', 'success');
    } catch (error) {
        showToast('Failed to read clipboard', 'error');
    }
}

async function handleDeanonymize() {
    const text = elements.deanonInput.value.trim();
    if (!text) {
        showToast('Please enter anonymized text', 'error');
        return;
    }

    if (!isConnected) {
        showToast('Not connected to API. Check settings.', 'error');
        return;
    }

    elements.deanonymizeBtn.disabled = true;
    elements.deanonymizeBtn.classList.add('loading');

    try {
        const response = await fetch(`${apiUrl}/api/deanonymize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        const data = await response.json();

        if (response.ok) {
            elements.deanonResult.textContent = data.deanonymized_text;
            elements.deanonResultGroup.style.display = 'block';
            showToast('Text deanonymized successfully!', 'success');
        } else {
            throw new Error(data.error || 'Deanonymization failed');
        }
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.deanonymizeBtn.disabled = false;
        elements.deanonymizeBtn.classList.remove('loading');
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
        .then(() => showToast('Copied to clipboard!', 'success'))
        .catch(() => showToast('Failed to copy', 'error'));
}

function showToast(message, type = '') {
    elements.toast.textContent = message;
    elements.toast.className = `toast show ${type}`;
    setTimeout(() => {
        elements.toast.className = 'toast';
    }, 3000);
}

async function saveToHistory(item) {
    try {
        const result = await chrome.storage.local.get(CONFIG.STORAGE_KEYS.HISTORY);
        let history = result[CONFIG.STORAGE_KEYS.HISTORY] || [];

        history.unshift(item);
        if (history.length > CONFIG.MAX_HISTORY) {
            history = history.slice(0, CONFIG.MAX_HISTORY);
        }

        await chrome.storage.local.set({ [CONFIG.STORAGE_KEYS.HISTORY]: history });
        loadHistory();
    } catch (error) {
        console.error('Error saving history:', error);
    }
}

async function loadHistory() {
    try {
        const result = await chrome.storage.local.get(CONFIG.STORAGE_KEYS.HISTORY);
        const history = result[CONFIG.STORAGE_KEYS.HISTORY] || [];

        if (history.length === 0) {
            elements.historyList.innerHTML = '<p class="empty-state">No history yet</p>';
            return;
        }

        elements.historyList.innerHTML = history.map((item, index) => `
      <div class="history-item" data-index="${index}">
        <div class="history-item-header">
          <span class="mode-badge">${item.mode}</span>
          <span>${formatDate(item.timestamp)}</span>
        </div>
        <div class="history-item-text">${escapeHtml(item.original)}...</div>
      </div>
    `).join('');

        // Add click handlers for history items
        elements.historyList.querySelectorAll('.history-item').forEach(el => {
            el.addEventListener('click', () => {
                const index = parseInt(el.dataset.index);
                const item = history[index];
                if (item) {
                    elements.inputText.value = item.original;
                    elements.charCount.textContent = item.original.length;
                    switchTab('anonymize');
                }
            });
        });
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

async function clearHistory() {
    try {
        await chrome.storage.local.remove(CONFIG.STORAGE_KEYS.HISTORY);
        loadHistory();
        showToast('History cleared', 'success');
    } catch (error) {
        showToast('Failed to clear history', 'error');
    }
}

function formatDate(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
