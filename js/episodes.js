/**
 * OrthoDigest Episode Browser
 * Fetches episodes from Transistor API and renders interactive cards
 * with subspecialty filtering and keyword search.
 */

const TRANSISTOR_API_KEY = ''; // Populated at build time or fetched from episodes.json
const SHOW_ID = '76191';

// Subspecialty rotation mapping
const SUBSPECIALTIES = {
  0: 'Hip',        // Monday episodes (1, 8, 15, 22, ...)
  1: 'Knee',
  2: 'Shoulder & Elbow',
  3: 'Foot & Ankle',
  4: 'Hand',
  5: 'Trauma',
  6: 'Sports Medicine'
};

let allEpisodes = [];

/**
 * Load episodes from a static JSON file (generated at build time)
 * This avoids exposing the Transistor API key in client-side code.
 */
async function loadEpisodes() {
  try {
    const response = await fetch('../data/episodes.json');
    if (!response.ok) throw new Error('Could not load episodes');
    allEpisodes = await response.json();
    renderEpisodes(allEpisodes);
  } catch (err) {
    console.error('Failed to load episodes:', err);
    document.getElementById('episodesGrid').innerHTML =
      '<p style="text-align: center; color: var(--jvo-text-light);">Unable to load episodes. Please try again later.</p>';
  }
}

/**
 * Render episode cards into the grid
 */
function renderEpisodes(episodes) {
  const grid = document.getElementById('episodesGrid');

  if (!episodes.length) {
    grid.innerHTML = '<p style="text-align: center; color: var(--jvo-text-light); padding: 2rem 0;">No episodes match your filters.</p>';
    return;
  }

  grid.innerHTML = episodes.map(ep => `
    <div class="episode-card" data-sub="${ep.subspecialty}" onclick="this.classList.toggle('expanded')">
      <div class="episode-card-header">
        <h3>${ep.title}</h3>
        <span class="episode-tag" data-sub="${ep.subspecialty}">${ep.subspecialty}</span>
      </div>
      <div class="episode-card-meta">
        Vol. ${ep.volume}, Issue ${ep.issue} &middot; ${ep.duration || ''} &middot; ${ep.manuscript_count || 6} manuscripts
      </div>
      <div class="episode-card-description">
        ${ep.description || ''}
        ${ep.manuscripts ? `
          <ul class="manuscript-list">
            ${ep.manuscripts.map(ms => `
              <li>
                <strong>${ms.author}</strong> &mdash; ${ms.title}
                ${ms.doi ? `<br><a href="https://doi.org/${ms.doi}" target="_blank">DOI: ${ms.doi}</a>` : ''}
              </li>
            `).join('')}
          </ul>
        ` : ''}
        ${ep.share_url ? `
          <div class="episode-player">
            <audio controls preload="none" src="${ep.media_url}"></audio>
          </div>
        ` : ''}
      </div>
    </div>
  `).join('');
}

/**
 * Filter by subspecialty
 */
function setupFilters() {
  const filterBar = document.getElementById('filterBar');
  if (!filterBar) return;

  filterBar.addEventListener('click', (e) => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;

    // Update active state
    filterBar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const sub = btn.dataset.sub;
    const searchTerm = document.getElementById('searchInput')?.value.toLowerCase() || '';

    let filtered = allEpisodes;
    if (sub !== 'all') {
      filtered = filtered.filter(ep => ep.subspecialty === sub);
    }
    if (searchTerm) {
      filtered = filtered.filter(ep => matchesSearch(ep, searchTerm));
    }
    renderEpisodes(filtered);
  });
}

/**
 * Search episodes
 */
function setupSearch() {
  const input = document.getElementById('searchInput');
  if (!input) return;

  let debounceTimer;
  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const searchTerm = input.value.toLowerCase();
      const activeSub = document.querySelector('.filter-btn.active')?.dataset.sub || 'all';

      let filtered = allEpisodes;
      if (activeSub !== 'all') {
        filtered = filtered.filter(ep => ep.subspecialty === activeSub);
      }
      if (searchTerm) {
        filtered = filtered.filter(ep => matchesSearch(ep, searchTerm));
      }
      renderEpisodes(filtered);
    }, 300);
  });
}

/**
 * Check if an episode matches a search term
 */
function matchesSearch(ep, term) {
  const searchable = [
    ep.title,
    ep.subspecialty,
    ep.description,
    ...(ep.manuscripts || []).map(ms => `${ms.title} ${ms.author}`),
  ].join(' ').toLowerCase();
  return searchable.includes(term);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  loadEpisodes();
  setupFilters();
  setupSearch();
});
