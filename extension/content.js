/**
 * PII Anonymizer Extension - Content Script
 * Injects UI elements for showing results on web pages
 */

// Create overlay container
let overlayContainer = null;

function createOverlayContainer() {
    if (overlayContainer) return overlayContainer;

    overlayContainer = document.createElement('div');
    overlayContainer.id = 'pii-anonymizer-overlay';
    document.body.appendChild(overlayContainer);
    return overlayContainer;
}

function showNotification(message, type = 'info') {
    const container = createOverlayContainer();

    const notification = document.createElement('div');
    notification.className = `pii-notification pii-notification-${type}`;
    notification.innerHTML = `
    <div class="pii-notification-content">
      <span class="pii-notification-icon">${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span>
      <span class="pii-notification-message">${message}</span>
    </div>
    <button class="pii-notification-close">×</button>
  `;

    container.appendChild(notification);

    // Add close handler
    notification.querySelector('.pii-notification-close').addEventListener('click', () => {
        notification.classList.add('pii-notification-hide');
        setTimeout(() => notification.remove(), 300);
    });

    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.classList.add('pii-notification-hide');
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

function showResultModal(data) {
    const container = createOverlayContainer();

    // Remove existing modal if any
    const existing = container.querySelector('.pii-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.className = 'pii-modal';
    modal.innerHTML = `
    <div class="pii-modal-backdrop"></div>
    <div class="pii-modal-content">
      <div class="pii-modal-header">
        <h3>🔒 PII Anonymizer Result</h3>
        <button class="pii-modal-close">×</button>
      </div>
      <div class="pii-modal-body">
        <div class="pii-result-section">
          <label>Original Text:</label>
          <div class="pii-result-box pii-original">${escapeHtml(data.original)}</div>
        </div>
        <div class="pii-result-section">
          <label>Anonymized Text:</label>
          <div class="pii-result-box pii-anonymized">${escapeHtml(data.anonymized)}</div>
        </div>
        <div class="pii-result-info">
          Mode: <strong>${data.mode}</strong> | Entities found: <strong>${data.mappingsCount}</strong>
        </div>
      </div>
      <div class="pii-modal-footer">
        <button class="pii-btn pii-btn-secondary pii-copy-original">Copy Original</button>
        <button class="pii-btn pii-btn-primary pii-copy-anonymized">Copy Anonymized</button>
      </div>
    </div>
  `;

    container.appendChild(modal);

    // Event handlers
    const closeModal = () => {
        modal.classList.add('pii-modal-hide');
        setTimeout(() => modal.remove(), 300);
    };

    modal.querySelector('.pii-modal-close').addEventListener('click', closeModal);
    modal.querySelector('.pii-modal-backdrop').addEventListener('click', closeModal);

    modal.querySelector('.pii-copy-original').addEventListener('click', () => {
        navigator.clipboard.writeText(data.original);
        showNotification('Original text copied!', 'success');
    });

    modal.querySelector('.pii-copy-anonymized').addEventListener('click', () => {
        navigator.clipboard.writeText(data.anonymized);
        showNotification('Anonymized text copied!', 'success');
    });

    // If copy to clipboard was requested, do it automatically
    if (data.copyToClipboard) {
        navigator.clipboard.writeText(data.anonymized);
        showNotification('Anonymized text copied to clipboard!', 'success');
    }

    // Focus trap
    modal.querySelector('.pii-modal-content').focus();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'showAnonymizedResult') {
        showResultModal(request.data);
        sendResponse({ success: true });
    } else if (request.action === 'showError') {
        showNotification(request.message, 'error');
        sendResponse({ success: true });
    }
    return true;
});

// Keyboard shortcut handler
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + Shift + A to anonymize selected text
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'A') {
        const selectedText = window.getSelection().toString().trim();
        if (selectedText) {
            e.preventDefault();
            chrome.runtime.sendMessage({
                action: 'quickAnonymize',
                text: selectedText
            });
        }
    }
});
