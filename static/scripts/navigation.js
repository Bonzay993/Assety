function setupNavigation() {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('toggle-btn');
    const categories = document.getElementById('categories-btn');
    const dropdown = document.getElementById('categories-menu');
    const arrow = document.getElementById('dropdown-arrow');
    if (!sidebar || !toggle || !categories || !dropdown) return;
    const mobile = window.matchMedia('(max-width: 767px)');
    let desktopCollapsed = false;

    function setDropdown(open) {
        dropdown.classList.toggle('show', open);
        categories.setAttribute('aria-expanded', String(open));
        if (arrow) {
            arrow.classList.toggle('fa-chevron-down', open);
            arrow.classList.toggle('fa-chevron-left', !open);
        }
    }

    function updateToggle() {
        const expanded = mobile.matches ? sidebar.classList.contains('mobile-open') : !desktopCollapsed;
        toggle.setAttribute('aria-expanded', String(expanded));
        toggle.setAttribute('aria-label', expanded ? 'Collapse navigation' : 'Expand navigation');
    }

    function resize() {
        sidebar.classList.remove('mobile-open');
        sidebar.classList.toggle('minimized', !mobile.matches && desktopCollapsed);
        setDropdown(false);
        updateToggle();
    }

    function toggleNavigation() {
        if (mobile.matches) sidebar.classList.toggle('mobile-open');
        else {
            desktopCollapsed = !desktopCollapsed;
            sidebar.classList.toggle('minimized', desktopCollapsed);
        }
        setDropdown(false);
        updateToggle();
    }
    function toggleDropdown() { setDropdown(!dropdown.classList.contains('show')); }
    function handleKey(event) {
        if (event.key !== 'Escape') return;
        if (mobile.matches && sidebar.classList.contains('mobile-open')) {
            sidebar.classList.remove('mobile-open');
            setDropdown(false);
            updateToggle();
            toggle.focus();
        } else if (dropdown.classList.contains('show')) {
            setDropdown(false);
            categories.focus();
        }
    }
    function handleOutsideClick(event) {
        if (mobile.matches && sidebar.classList.contains('mobile-open') && !sidebar.contains(event.target)) {
            sidebar.classList.remove('mobile-open');
            setDropdown(false);
            updateToggle();
        }
    }
    toggle.addEventListener('click', toggleNavigation);
    categories.addEventListener('click', toggleDropdown);
    document.addEventListener('keydown', handleKey);
    document.addEventListener('click', handleOutsideClick);
    mobile.addEventListener('change', resize);
    resize();
    return () => {
        toggle.removeEventListener('click', toggleNavigation);
        categories.removeEventListener('click', toggleDropdown);
        document.removeEventListener('keydown', handleKey);
        document.removeEventListener('click', handleOutsideClick);
        mobile.removeEventListener('change', resize);
    };
}

if (typeof module !== 'undefined') module.exports = { setupNavigation };
else setupNavigation();
