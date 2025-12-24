/**
 * Mahjong Score Tracker - Application JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips and popovers if Bootstrap is available
    initializeUI();
});

/**
 * Initialize UI components
 */
function initializeUI() {
    // Add smooth scrolling
    enableSmoothScroll();
    
    // Initialize form validation
    initializeFormValidation();
    
    // Initialize dynamic features
    initializeDynamicFeatures();
}

/**
 * Enable smooth scrolling for anchor links
 */
function enableSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });
}

/**
 * Initialize form validation
 */
function initializeFormValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Check for required fields
            const requiredInputs = form.querySelectorAll('[required]');
            
            requiredInputs.forEach(input => {
                if (!input.value.trim()) {
                    e.preventDefault();
                    input.classList.add('is-invalid');
                    input.focus();
                } else {
                    input.classList.remove('is-invalid');
                }
            });
        });
    });
}

/**
 * Initialize dynamic features
 */
function initializeDynamicFeatures() {
    // Add active class to current nav link
    const currentPath = window.location.pathname;
    document.querySelectorAll('nav a').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

/**
 * Utility function to show alerts
 * @param {string} message - Alert message
 * @param {string} type - Alert type (success, danger, info, warning)
 * @param {number} duration - Duration in milliseconds (0 = permanent)
 */
function showAlert(message, type = 'info', duration = 5000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.textContent = message;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        
        if (duration > 0) {
            setTimeout(() => {
                alertDiv.remove();
            }, duration);
        }
    }
}

/**
 * Utility function to confirm actions
 * @param {string} message - Confirmation message
 * @returns {boolean} - User's choice
 */
function confirmAction(message) {
    return confirm(message);
}

/**
 * Format numbers with thousand separators
 * @param {number} num - Number to format
 * @returns {string} - Formatted number
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Convert score for display
 * @param {number} rawScore - Raw Mahjong score
 * @returns {number} - Formatted score
 */
function formatMahjongScore(rawScore) {
    return Math.round((rawScore - 30000) / 1000 * 100) / 100;
}
