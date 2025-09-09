if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    const input = document.querySelector('.search-input');
    const icon = document.querySelector('.search-icon');
    const results = document.getElementById('search-results');

    async function performSearch() {
      const query = input.value.trim();
      if (!query) {
        results.innerHTML = '';
        results.style.display = 'none';
        return;
      }
      try {
        const response = await fetch(`/search-assets?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        results.innerHTML = '';
        if (!data.results.length) {
          const p = document.createElement('p');
          p.textContent = 'No assets found';
          results.appendChild(p);
        } else {
          data.results.forEach(item => {
            const link = document.createElement('a');
            link.href = `/asset/${item.id}`;
            link.textContent = item.asset_tag;
            results.appendChild(link);
          });
        }
        results.style.display = 'block';
      } catch (err) {
        console.error('Search error', err);
      }
    }

    icon.addEventListener('click', performSearch);
    input.addEventListener('keyup', e => {
      if (e.key === 'Enter') {
        performSearch();
      }
    });
  });
}