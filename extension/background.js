/**
 * PII Anonymizer Extension - Background Service Worker
 * Handles context menus and background tasks
 */

// Configuration
const CONFIG = {
    STORAGE_KEYS: {
        API_URL: 'pii_api_url',
        SETTINGS: 'pii_settings'
    },
    DEFAULT_API_URL: 'http://localhost:5000'
};

// Initialize extension
chrome.runtime.onInstalled.addListener(async (details) => {
    console.log('PII Anonymizer extension installed:', details.reason);

    // Set up default settings
    const result = await chrome.storage.sync.get(CONFIG.STORAGE_KEYS.API_URL);
    if (!result[CONFIG.STORAGE_KEYS.API_URL]) {
        await chrome.storage.sync.set({
            [CONFIG.STORAGE_KEYS.API_URL]: CONFIG.DEFAULT_API_URL
        });
    }

    // Create context menu items
    createContextMenus();
});

// Create context menus
function createContextMenus() {
    // Remove existing menus first
    chrome.contextMenus.removeAll(() => {
        // Main menu item
        chrome.contextMenus.create({
            id: 'pii-anonymizer-parent',
            title: '🔒 PII Anonymizer',
            contexts: ['selection']
        });

        // Submenu items for different modes
        chrome.contextMenus.create({
            id: 'pii-pseudonymize',
            parentId: 'pii-anonymizer-parent',
            title: 'Pseudonymize (Reversible)',
            contexts: ['selection']
        });

        chrome.contextMenus.create({
            id: 'pii-mask',
            parentId: 'pii-anonymizer-parent',
            title: 'Mask (J*** D***)',
            contexts: ['selection']
        });

        chrome.contextMenus.create({
            id: 'pii-replace',
            parentId: 'pii-anonymizer-parent',
            title: 'Replace ([Person Name])',
            contexts: ['selection']
        });

        chrome.contextMenus.create({
            id: 'pii-separator',
            parentId: 'pii-anonymizer-parent',
            type: 'separator',
            contexts: ['selection']
        });

        chrome.contextMenus.create({
            id: 'pii-copy-anonymized',
            parentId: 'pii-anonymizer-parent',
            title: 'Copy Anonymized to Clipboard',
            contexts: ['selection']
        });
    });
}

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
    const selectedText = info.selectionText;
    if (!selectedText) return;

    let mode = 'pseudonymize';
    let copyToClipboard = false;

    switch (info.menuItemId) {
        case 'pii-pseudonymize':
            mode = 'pseudonymize';
            break;
        case 'pii-mask':
            mode = 'mask';
            break;
        case 'pii-replace':
            mode = 'replace';
            break;
        case 'pii-copy-anonymized':
            mode = 'pseudonymize';
            copyToClipboard = true;
            break;
        default:
            return;
    }

    try {
        const result = await chrome.storage.sync.get(CONFIG.STORAGE_KEYS.API_URL);
        const apiUrl = result[CONFIG.STORAGE_KEYS.API_URL] || CONFIG.DEFAULT_API_URL;

        const response = await fetch(`${apiUrl}/api/anonymize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: selectedText,
                mode: mode,
                call_llm: false
            })
        });

        const data = await response.json();

        if (response.ok) {
            // Send result to content script
            chrome.tabs.sendMessage(tab.id, {
                action: 'showAnonymizedResult',
                data: {
                    original: selectedText,
                    anonymized: data.anonymized_text,
                    mode: mode,
                    mappingsCount: data.mappings_count,
                    copyToClipboard: copyToClipboard
                }
            });
        } else {
            chrome.tabs.sendMessage(tab.id, {
                action: 'showError',
                message: data.error || 'Anonymization failed'
            });
        }
    } catch (error) {
        chrome.tabs.sendMessage(tab.id, {
            action: 'showError',
            message: 'Failed to connect to API. Please check settings.'
        });
    }
});

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'getApiUrl') {
        chrome.storage.sync.get(CONFIG.STORAGE_KEYS.API_URL).then(result => {
            sendResponse({ apiUrl: result[CONFIG.STORAGE_KEYS.API_URL] || CONFIG.DEFAULT_API_URL });
        });
        return true; // Required for async response
    }

    if (request.action === 'setApiUrl') {
        chrome.storage.sync.set({ [CONFIG.STORAGE_KEYS.API_URL]: request.apiUrl }).then(() => {
            sendResponse({ success: true });
        });
        return true;
    }
});

// Handle extension icon click when popup is disabled
chrome.action.onClicked.addListener((tab) => {
    // This only fires if popup.html is not set
    // We have popup.html set, so this won't fire
});
