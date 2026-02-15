/**
 * PII Anonymizer Extension - Options Page Script
 * Handles settings and configuration
 */

const CONFIG = {
    STORAGE_KEYS: {
        API_URL: 'pii_api_url',
        SETTINGS: 'pii_settings'
    },
    DEFAULT_API_URL: 'http://localhost:5000'
};

// DOM Elements - will be populated after DOM loads
let elements = {};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', init);

function init() {
    // Cache elements after DOM is ready
    elements = {
        apiUrl: document.getElementById('apiUrl'),
        testBtn: document.getElementById('testBtn'),
        saveBtn: document.getElementById('saveBtn'),
        statusContainer: document.getElementById('statusContainer'),
        autoLlm: document.getElementById('autoLlm'),
        defaultMode: document.getElementById('defaultMode'),
        resetBtn: document.getElementById('resetBtn'),
        saveSettingsBtn: document.getElementById('saveSettingsBtn')
    };

    // Set up event listeners
    setupEventListeners();

    // Load saved settings
    loadSettings();
}

function setupEventListeners() {
    elements.testBtn.addEventListener('click', testConnection);
    elements.saveBtn.addEventListener('click', saveApiUrl);
    elements.saveSettingsBtn.addEventListener('click', savePreferences);
    elements.resetBtn.addEventListener('click', resetToDefaults);
}

async function loadSettings() {
    try {
        const result = await chrome.storage.sync.get([
            CONFIG.STORAGE_KEYS.API_URL,
            CONFIG.STORAGE_KEYS.SETTINGS
        ]);

        elements.apiUrl.value = result[CONFIG.STORAGE_KEYS.API_URL] || CONFIG.DEFAULT_API_URL;

        const settings = result[CONFIG.STORAGE_KEYS.SETTINGS] || {};
        elements.autoLlm.checked = settings.autoLlm || false;
        elements.defaultMode.value = settings.defaultMode || 'pseudonymize';
    } catch (error) {
        console.error('Error loading settings:', error);
        showStatus('Error loading settings: ' + error.message, 'error');
    }
}

async function testConnection() {
    const apiUrl = elements.apiUrl.value.trim();
    if (!apiUrl) {
        showStatus('Please enter an API URL', 'error');
        return;
    }

    showStatus('Testing connection...', 'checking');

    try {
        const response = await fetch(`${apiUrl}/api/health`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const data = await response.json();
            showStatus(`✓ Connected! API version: ${data.version || 'unknown'}, LLM mode: ${data.llm_mode || 'unknown'}`, 'success');
        } else {
            showStatus('API responded but returned an error', 'error');
        }
    } catch (error) {
        showStatus(`Connection failed: ${error.message}`, 'error');
    }
}

async function saveApiUrl() {
    const apiUrl = elements.apiUrl.value.trim();
    if (!apiUrl) {
        showStatus('Please enter an API URL', 'error');
        return;
    }

    try {
        await chrome.storage.sync.set({ [CONFIG.STORAGE_KEYS.API_URL]: apiUrl });
        showStatus('✓ API URL saved successfully!', 'success');
    } catch (error) {
        console.error('Error saving API URL:', error);
        showStatus('Failed to save settings: ' + error.message, 'error');
    }
}

async function savePreferences() {
    try {
        const settings = {
            autoLlm: elements.autoLlm.checked,
            defaultMode: elements.defaultMode.value
        };
        await chrome.storage.sync.set({ [CONFIG.STORAGE_KEYS.SETTINGS]: settings });
        showStatus('✓ Preferences saved!', 'success');
    } catch (error) {
        console.error('Error saving preferences:', error);
        showStatus('Failed to save preferences: ' + error.message, 'error');
    }
}

function resetToDefaults() {
    elements.apiUrl.value = CONFIG.DEFAULT_API_URL;
    elements.autoLlm.checked = false;
    elements.defaultMode.value = 'pseudonymize';
    showStatus('Settings reset to defaults (not saved yet)', 'success');
}

function showStatus(message, type) {
    elements.statusContainer.innerHTML = `<div class="status ${type}">${message}</div>`;
}
