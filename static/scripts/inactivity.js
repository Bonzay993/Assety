function setupInactivityTimer(idleMinutes = 2) {
    const modal = document.getElementById('inactivity-modal');
    const content = document.getElementById('modal-content');
    const countdown = document.getElementById('countdown');
    const stayButton = document.getElementById('stay-logged-in');
    if (!modal || !content || !countdown || !stayButton) return;

    const idleLimit = (Number(idleMinutes) > 0 ? Number(idleMinutes) : 2) * 60;
    let idleSeconds = 0;
    let remaining = 30;
    let loggedOut = false;
    let previousFocus;
    modal.addEventListener('keydown', event => {
        if (event.key === 'Tab' && !loggedOut) {
            event.preventDefault();
            stayButton.focus();
        }
    });
    const resetOnActivity = () => {
        if (!loggedOut && modal.style.display !== 'flex') idleSeconds = 0;
    };
    stayButton.addEventListener('click', () => {
        if (loggedOut) return;
        modal.style.display = 'none';
        idleSeconds = 0;
        remaining = 30;
        if (previousFocus?.isConnected) previousFocus.focus();
    });
    ['mousemove', 'keydown', 'scroll', 'click'].forEach(event => {
        window.addEventListener(event, resetOnActivity);
    });
    const timer = setInterval(async () => {
        if (loggedOut) return;
        if (modal.style.display === 'flex') {
            remaining -= 1;
            countdown.textContent = remaining;
            if (remaining === 0) {
                loggedOut = true;
                clearInterval(timer);
                try {
                    const response = await fetch('/logout', {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || '',
                            'X-Requested-With': 'fetch'
                        }
                    });
                    if (!response.ok) throw new Error('Logout failed');
                    content.innerHTML = '<h2>You have been logged out</h2><p>Session expired due to inactivity.</p><a href="/login">Go to Login</a>';
                    content.querySelector('a').focus();
                } catch (error) {
                    window.location.assign('/logout');
                }
            }
        } else if (++idleSeconds >= idleLimit) {
            remaining = 30;
            countdown.textContent = remaining;
            modal.style.display = 'flex';
            previousFocus = document.activeElement;
            stayButton.focus();
        }
    }, 1000);
    return timer;
}

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        const script = document.getElementById('idle-timer-script');
        if (script) setupInactivityTimer(script.dataset.timeout);
    });
}
if (typeof module !== 'undefined') module.exports = { setupInactivityTimer };
