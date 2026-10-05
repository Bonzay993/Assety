function setupSearch() {
  const input = document.querySelector('.search-input');
  const icon = document.querySelector('.search-icon');
  const suggestions = document.querySelector('.search-suggestions');
  if (!input || !icon || !suggestions || input.dataset.searchInitialized) return;
  input.dataset.searchInitialized = 'true';
  let sequence = 0;

  function navigate() {
    const query = input.value.trim();
    if (query) window.location.href = '/search?q=' + encodeURIComponent(query);
  }
  icon.addEventListener('click', navigate);
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); navigate(); }
  });
  input.addEventListener('input', async () => {
    const current = ++sequence;
    const query = input.value.trim();
    suggestions.replaceChildren();
    if (!query) return;
    try {
      const response = await fetch('/search_assets?q=' + encodeURIComponent(query));
      if (!response.ok || current !== sequence) return;
      const data = await response.json();
      if (current !== sequence) return;
      suggestions.replaceChildren();
      data.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item.asset_tag;
        li.addEventListener('click', () => {
          window.location.href = '/asset/' + encodeURIComponent(item.id);
        });
        suggestions.appendChild(li);
      });
    } catch (error) {
      if (current === sequence) suggestions.replaceChildren();
    }
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.search-bar')) {
      sequence += 1;
      suggestions.replaceChildren();
    }
  });
}

if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', setupSearch);
if (typeof module !== 'undefined') module.exports = { setupSearch };
