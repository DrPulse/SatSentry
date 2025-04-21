/**
 * Main JavaScript for SatSentry
 */

// Format timestamps to local time
function formatTimestamps() {
    document.querySelectorAll('[data-timestamp]').forEach(function(element) {
        const timestamp = element.getAttribute('data-timestamp');
        if (timestamp) {
            try {
                const date = new Date(timestamp);
                element.textContent = date.toLocaleString();
            } catch (e) {
                console.error('Error formatting timestamp:', e);
            }
        }
    });
}

// Show loading overlay
function showLoading() {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="spinner-border text-primary loading-spinner" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    document.body.appendChild(overlay);
}

// Hide loading overlay
function hideLoading() {
    const overlay = document.querySelector('.loading-overlay');
    if (overlay) {
        overlay.remove();
    }
}

// Copy to clipboard
function copyToClipboard(text) {
    // Use the newer Clipboard API if available
    if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text);
    }

    // Fallback to the older method
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    return Promise.resolve();
}

// Initialize tooltips
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Initialize on document ready
document.addEventListener('DOMContentLoaded', function() {
    // Format timestamps


    // Initialize tooltips
    initTooltips();

    // Add copy functionality to address codes
    document.querySelectorAll('.address-code').forEach(function(element) {
        // Store the original text
        const text = element.textContent.trim();

        // Add click event listener
        element.addEventListener('click', function() {
            // Add copied class to change the tooltip
            element.classList.add('copied');

            // Copy to clipboard
            copyToClipboard(text)
                .then(() => {
                    // Remove copied class after a delay
                    setTimeout(() => {
                        element.classList.remove('copied');
                    }, 1500);
                })
                .catch(err => {
                    console.error('Failed to copy text: ', err);
                    // Still remove the class after a delay
                    setTimeout(() => {
                        element.classList.remove('copied');
                    }, 1500);
                });
        });
    });

    // Add form submission loading
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function() {
            showLoading();
        });
    });

    // Handle form validation
    document.querySelectorAll('input[required]').forEach(function(input) {
        input.addEventListener('blur', function() {
            if (this.value.trim()) {
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            } else {
                this.classList.remove('is-valid');
                this.classList.add('is-invalid');
            }
        });
    });
});
