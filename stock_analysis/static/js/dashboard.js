// Dashboard logic

let stockData = [];
let searchSuggestions = [];
let activeSuggestion = -1;
let searchDebounce = null;

async function runScan() {
    const sector = document.getElementById('sector-filter').value;
    const maxPrice = document.getElementById('max-price').value;
    const statusEl = document.getElementById('scan-status');
    const scanText = document.getElementById('scan-text');
    const scanBtn = document.getElementById('scan-btn');

    statusEl.style.display = 'flex';
    scanBtn.disabled = true;
    scanText.textContent = 'Scanning...';

    try {
        const resp = await fetch('/api/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({sector, max_price: parseFloat(maxPrice)})
        });
        const data = await resp.json();
        stockData = data.results || [];
        renderTable(stockData);
        showFreshnessBanner(stockData);
        scanText.textContent = `${stockData.length} stocks found`;
    } catch (e) {
        scanText.textContent = 'Scan failed: ' + e.message;
    }
    scanBtn.disabled = false;
    setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
}

async function runScanAll() {
    const maxPrice = document.getElementById('max-price').value;
    const statusEl = document.getElementById('scan-status');
    const scanText = document.getElementById('scan-text');
    const btn = document.getElementById('scan-all-btn');

    statusEl.style.display = 'flex';
    btn.disabled = true;
    scanText.textContent = 'Scanning all NSE stocks (this may take a few minutes)...';

    try {
        const resp = await fetch('/api/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({sector: 'all', max_price: parseFloat(maxPrice), scan_all: true})
        });
        const data = await resp.json();
        stockData = data.results || [];
        renderTable(stockData);
        showFreshnessBanner(stockData);
        scanText.textContent = `${stockData.length} stocks found`;
    } catch (e) {
        scanText.textContent = 'Scan failed: ' + e.message;
    }
    btn.disabled = false;
    setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
}

// ── Search ─────────────────────────────────────────────────────────────────

function onSearchInput() {
    clearTimeout(searchDebounce);
    const q = document.getElementById('stock-search').value.trim();
    if (q.length < 1) { hideDropdown(); return; }
    searchDebounce = setTimeout(() => fetchSuggestions(q), 200);
}

async function fetchSuggestions(q) {
    try {
        const resp = await fetch(`/api/stocks?q=${encodeURIComponent(q)}`);
        const data = await resp.json();
        searchSuggestions = data.results || [];
        activeSuggestion = -1;
        renderDropdown();
    } catch (e) {
        hideDropdown();
    }
}

function renderDropdown() {
    const dd = document.getElementById('search-dropdown');
    if (!searchSuggestions.length) { hideDropdown(); return; }
    dd.innerHTML = searchSuggestions.slice(0, 8).map((s, i) =>
        `<div class="suggestion-item" data-i="${i}" data-ticker="${s.ticker}"
              onmousedown="selectSuggestion(${i})"
              onmouseover="highlightSuggestion(${i})">
            <span class="sug-ticker">${s.ticker.replace('.NS','')}</span>
            <span class="sug-name">${s.name}</span>
            <span class="sug-sector">${s.sector}</span>
         </div>`
    ).join('');
    dd.style.display = 'block';
}

function hideDropdown() {
    const dd = document.getElementById('search-dropdown');
    dd.style.display = 'none';
    searchSuggestions = [];
    activeSuggestion = -1;
}

function highlightSuggestion(i) {
    activeSuggestion = i;
    document.querySelectorAll('.suggestion-item').forEach((el, j) => {
        el.classList.toggle('active', j === i);
    });
}

function selectSuggestion(i) {
    const s = searchSuggestions[i];
    if (s) {
        document.getElementById('stock-search').value = s.ticker;
        hideDropdown();
        window.location = `/stock/${encodeURIComponent(s.ticker)}`;
    }
}

function onSearchKey(e) {
    const items = document.querySelectorAll('.suggestion-item');
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeSuggestion = Math.min(activeSuggestion + 1, items.length - 1);
        highlightSuggestion(activeSuggestion);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeSuggestion = Math.max(activeSuggestion - 1, 0);
        highlightSuggestion(activeSuggestion);
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (activeSuggestion >= 0 && searchSuggestions[activeSuggestion]) {
            selectSuggestion(activeSuggestion);
        } else {
            analyseSearched();
        }
    } else if (e.key === 'Escape') {
        hideDropdown();
    }
}

// Hide dropdown when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrap')) hideDropdown();
});

async function analyseSearched() {
    let ticker = document.getElementById('stock-search').value.trim().toUpperCase();
    if (!ticker) return;
    // Auto-append .NS if no exchange suffix
    if (!ticker.includes('.')) ticker = ticker + '.NS';
    window.location = `/stock/${encodeURIComponent(ticker)}`;
}

// ── Freshness banner ───────────────────────────────────────────────────────

function showFreshnessBanner(data) {
    const banner = document.getElementById('freshness-banner');
    if (!data.length) { banner.style.display = 'none'; return; }

    const ages = data.filter(s => s.data_age_days != null).map(s => s.data_age_days);
    if (!ages.length) { banner.style.display = 'none'; return; }

    const maxAge = Math.max(...ages);
    const avgAge = (ages.reduce((a, b) => a + b, 0) / ages.length).toFixed(1);
    const staleCount = ages.filter(a => a > 3).length;

    let cls = 'freshness-ok';
    let msg = `Data freshness: most recent data is ${Math.min(...ages)} day(s) old, avg ${avgAge} days.`;
    if (staleCount > 0) {
        cls = 'freshness-warn';
        msg = `⚠ Data freshness warning: ${staleCount} stock(s) have data older than 3 days (max ${maxAge} days). This may indicate a market holiday or data source issue.`;
    }
    if (maxAge > 7) {
        cls = 'freshness-stale';
        msg = `⛔ Stale data: ${staleCount} stock(s) have data older than 7 days (max ${maxAge} days). Analysis may be unreliable — check your data source.`;
    }

    banner.className = `freshness-banner ${cls}`;
    banner.textContent = msg;
    banner.style.display = 'block';
}

// ── Freshness badge helper ─────────────────────────────────────────────────

function freshnessBadge(dataDate, ageDays) {
    if (!dataDate) return '<span class="fresh-badge fresh-unknown">N/A</span>';
    let cls = 'fresh-ok';
    if (ageDays > 7)      cls = 'fresh-stale';
    else if (ageDays > 3) cls = 'fresh-warn';
    return `<span class="fresh-badge ${cls}" title="${ageDays} day(s) ago">${dataDate}</span>`;
}

// ── Render table ───────────────────────────────────────────────────────────

function renderTable(data) {
    const tbody = document.getElementById('stock-tbody');
    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="empty-msg">No results found</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(s => {
        const sigClass = `signal-${s.signal.toLowerCase()}`;
        const badge = `<span class="signal-badge ${sigClass}">${s.signal}</span>`;
        const macdDir = s.indicators.macd_hist > 0 ? '+' : '';
        const dateBadge = freshnessBadge(s.data_date, s.data_age_days);
        return `
        <tr class="${sigClass} clickable" onclick="window.location='/stock/${encodeURIComponent(s.ticker)}'">
            <td><strong>${s.ticker.replace('.NS','')}</strong></td>
            <td>${s.name || ''}</td>
            <td>&#8377;${s.last_price.toFixed(2)}</td>
            <td>${badge}</td>
            <td>${s.confidence.toFixed(1)}%</td>
            <td>${s.score > 0 ? '+' : ''}${s.score.toFixed(3)}</td>
            <td>${s.indicators.rsi.toFixed(1)}</td>
            <td>${macdDir}${s.indicators.macd_hist.toFixed(4)}</td>
            <td>${dateBadge}</td>
            <td>${(s.notes || []).join(', ')}</td>
        </tr>`;
    }).join('');
}

// ── Sorting ────────────────────────────────────────────────────────────────

let sortDir = {};
function sortTable(col) {
    const key = col;
    sortDir[key] = !sortDir[key];
    const dir = sortDir[key] ? 1 : -1;

    stockData.sort((a, b) => {
        let va, vb;
        if (col <= 1) {
            va = col === 0 ? a.ticker : (a.name || '');
            vb = col === 0 ? b.ticker : (b.name || '');
            return va.localeCompare(vb) * dir;
        }
        if (col === 2) { va = a.last_price; vb = b.last_price; }
        else if (col === 3) { va = a.signal; vb = b.signal; return va.localeCompare(vb) * dir; }
        else if (col === 4) { va = a.confidence; vb = b.confidence; }
        else if (col === 5) { va = a.score; vb = b.score; }
        else if (col === 6) { va = a.indicators.rsi; vb = b.indicators.rsi; }
        else if (col === 7) { va = a.indicators.macd_hist; vb = b.indicators.macd_hist; }
        else if (col === 8) { va = a.data_age_days ?? 999; vb = b.data_age_days ?? 999; }
        return (va - vb) * dir;
    });
    renderTable(stockData);
}

// ── SSE handler ────────────────────────────────────────────────────────────

window.handleSSE = function(data) {
    if (data.type === 'scan_progress') {
        const scanText = document.getElementById('scan-text');
        if (scanText) scanText.textContent = data.message;
    }
};
