(() => {
  const input = document.querySelector('#search-input');
  const originalGrid = document.querySelector('#page-grid');
  const resultGrid = document.querySelector('#search-results');
  const status = document.querySelector('#search-status');
  if (!input || !originalGrid || !resultGrid || !status) return;

  let records = [];
  fetch('search.json')
    .then(response => response.ok ? response.json() : Promise.reject(new Error('search index unavailable')))
    .then(data => { records = data; })
    .catch(() => { status.textContent = 'Full-text search index could not be loaded. Title browsing still works.'; });

  const escapeHtml = value => String(value).replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character]);

  input.addEventListener('input', () => {
    const query = input.value.trim().toLocaleLowerCase();
    if (!query) {
      originalGrid.hidden = false;
      resultGrid.hidden = true;
      resultGrid.replaceChildren();
      status.textContent = '';
      return;
    }

    const terms = query.split(/\s+/).filter(Boolean);
    const matches = records.filter(record => {
      const haystack = `${record.title} ${record.title_de} ${record.text}`.toLocaleLowerCase();
      return terms.every(term => haystack.includes(term));
    }).slice(0, 100);

    resultGrid.innerHTML = matches.map(record => {
      const snippetStart = Math.max(0, record.text.toLocaleLowerCase().indexOf(terms[0]) - 80);
      const snippet = record.text.slice(snippetStart, snippetStart + 260);
      return `<article class="page-card"><h3><a href="${escapeHtml(record.href)}">${escapeHtml(record.title)}</a></h3><p>${escapeHtml(snippet)}${record.text.length > snippetStart + 260 ? '…' : ''}</p></article>`;
    }).join('');
    originalGrid.hidden = true;
    resultGrid.hidden = false;
    status.textContent = `${matches.length} matching page${matches.length === 1 ? '' : 's'}`;
  });
})();
