if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        const toggleBtn = document.getElementById('toggle-tips');
        const tipsPanel = document.getElementById('tips-panel');
        if (!toggleBtn || !tipsPanel) return;
        const showText = toggleBtn.getAttribute('data-show-text');
        const hideText = toggleBtn.getAttribute('data-hide-text');
        toggleBtn.addEventListener('click', () => {
            tipsPanel.classList.toggle('show');
            if (tipsPanel.classList.contains('show')) {
                toggleBtn.textContent = hideText;
            } else {
                toggleBtn.textContent = showText;
            }
        });
    });
}

// Export for testing if needed
if (typeof module !== 'undefined') {
    module.exports = {};
}