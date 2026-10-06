const { setupNavigation } = require('./navigation');

describe('responsive navigation', () => {
    let media, resize, cleanup;
    beforeEach(() => {
        document.body.innerHTML = `<aside id="sidebar"><button id="toggle-btn"></button><ul id="menu"><li><button id="categories-btn"></button><ul id="categories-menu"></ul><i id="dropdown-arrow"></i></li></ul></aside><main>Page content</main>`;
        media = { matches: true, addEventListener: jest.fn((event, callback) => { resize = callback; }), removeEventListener: jest.fn() };
        window.matchMedia = jest.fn(() => media);
        cleanup = setupNavigation();
    });
    afterEach(() => cleanup());

    test('mobile menu starts closed and opens without minimizing the sidebar', () => {
        const toggle = document.getElementById('toggle-btn');
        expect(toggle.getAttribute('aria-expanded')).toBe('false');
        toggle.click();
        expect(document.getElementById('sidebar').classList.contains('mobile-open')).toBe(true);
        expect(document.getElementById('sidebar').classList.contains('minimized')).toBe(false);
        expect(toggle.getAttribute('aria-expanded')).toBe('true');
    });

    test('Escape closes mobile navigation and returns keyboard focus', () => {
        document.getElementById('toggle-btn').click();
        document.getElementById('categories-btn').click();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(document.getElementById('sidebar').classList.contains('mobile-open')).toBe(false);
        expect(document.getElementById('categories-menu').classList.contains('show')).toBe(false);
        expect(document.activeElement.id).toBe('toggle-btn');
    });

    test('clicking page content closes mobile navigation', () => {
        document.getElementById('toggle-btn').click();
        document.querySelector('main').click();
        expect(document.getElementById('toggle-btn').getAttribute('aria-expanded')).toBe('false');
    });

    test('desktop collapse preserves access to the categories submenu', () => {
        media.matches = false;
        resize();
        document.getElementById('toggle-btn').click();
        expect(document.getElementById('sidebar').classList.contains('minimized')).toBe(true);
        document.getElementById('categories-btn').click();
        expect(document.getElementById('categories-btn').getAttribute('aria-expanded')).toBe('true');
        expect(document.getElementById('categories-menu').classList.contains('show')).toBe(true);
    });

    test('switching between phone and desktop resets open menus and restores desktop collapse', () => {
        media.matches = false;
        resize();
        document.getElementById('toggle-btn').click();
        media.matches = true;
        resize();
        expect(document.getElementById('sidebar').classList.contains('minimized')).toBe(false);
        document.getElementById('toggle-btn').click();
        document.getElementById('categories-btn').click();
        media.matches = false;
        resize();
        expect(document.getElementById('sidebar').classList.contains('mobile-open')).toBe(false);
        expect(document.getElementById('sidebar').classList.contains('minimized')).toBe(true);
        expect(document.getElementById('categories-btn').getAttribute('aria-expanded')).toBe('false');
    });

    test('Escape closes a desktop submenu without expanding the sidebar', () => {
        media.matches = false;
        resize();
        document.getElementById('toggle-btn').click();
        document.getElementById('categories-btn').click();
        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
        expect(document.getElementById('categories-btn').getAttribute('aria-expanded')).toBe('false');
        expect(document.getElementById('sidebar').classList.contains('minimized')).toBe(true);
        expect(document.activeElement.id).toBe('categories-btn');
    });
});
