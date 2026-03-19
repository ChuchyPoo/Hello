// Mutual Funds page logic

let currentFund = null;
let navChart = null;
let mfSearchSuggestions = [];
let mfSearchDebounce = null;

// ── Page init ────────────────────────────────────────────────────────────────

async function initFundsPage() {
    // Load NAVs for popular funds
    const placeholders = document.querySelectorAll('[id^="nav-"]');
    for (const el of placeholders) {
        const schemeCode = el.id.replace('nav-', '');
        loadQuickNAV(schemeCode, el);
    }
}

async function loadQuickNAV(schemeCode, el) {
    try {
        const resp = await fetch(`/api/mf/${schemeCode}`);
        const data = await resp.json();
        if (data.nav) {
            const retClass = (data.return_1y || 0) >= 0 ? 'ret-positive' : 'ret-negative';
            el.innerHTML = `
                <div class="fund-nav-value">NAV: ₹${data.nav.toFixed(2)}
                    <span class="fund-nav-date">(${data.nav_date})</span>
                </div>
                ${data.return_1y != null ? `<div class="fund-return ${retClass}">1Y: ${data.return_1y >= 0 ? '+' : ''}${data.return_1y}%</div>` : ''}
            `;
        } else {
            el.innerHTML = '<span class="text-muted">NAV unavailable</span>';
        }
    } catch (e) {
        el.innerHTML = '<span class="text-muted">Error</span>';
    }
}

// ── Search ───────────────────────────────────────────────────────────────────

function onMFSearchInput() {
    clearTimeout(mfSearchDebounce);
    const q = document.getElementById('mf-search').value.trim();
    if (q.length < 2) { hideMFDropdown(); return; }
    mfSearchDebounce = setTimeout(() => fetchMFSuggestions(q), 250);
}

async function fetchMFSuggestions(q) {
    try {
        const resp = await fetch(`/api/mf/search?q=${encodeURIComponent(q)}`);
        const data = await resp.json();
        mfSearchSuggestions = data.results || [];
        renderMFDropdown();
    } catch (e) {
        hideMFDropdown();
    }
}

function renderMFDropdown() {
    const dd = document.getElementById('mf-dropdown');
    if (!mfSearchSuggestions.length) { hideMFDropdown(); return; }
    dd.innerHTML = mfSearchSuggestions.slice(0, 8).map((f, i) =>
        `<div class="suggestion-item" onmousedown="selectMFSuggestion(${i})"
              onmouseover="document.querySelectorAll('#mf-dropdown .suggestion-item').forEach((el,j)=>el.classList.toggle('active',j===${i}))">
            <span class="sug-ticker">${f.fund_house || ''}</span>
            <span class="sug-name">${f.scheme_name || ''}</span>
            <span class="sug-sector">${f.scheme_category || ''}</span>
        </div>`
    ).join('');
    dd.style.display = 'block';
}

function hideMFDropdown() {
    document.getElementById('mf-dropdown').style.display = 'none';
}

function selectMFSuggestion(i) {
    const f = mfSearchSuggestions[i];
    if (f) {
        document.getElementById('mf-search').value = f.scheme_name;
        hideMFDropdown();
        loadFund(f.scheme_code);
    }
}

function onMFSearchKey(e) {
    if (e.key === 'Enter') { e.preventDefault(); searchFunds(); }
    else if (e.key === 'Escape') hideMFDropdown();
}

async function searchFunds() {
    hideMFDropdown();
    const q = document.getElementById('mf-search').value.trim();
    if (!q) return;

    setMFStatus(true, 'Searching...');
    try {
        const resp = await fetch(`/api/mf/search?q=${encodeURIComponent(q)}`);
        const data = await resp.json();
        renderSearchResults(data.results || []);
    } catch (e) {
        console.error(e);
    }
    setMFStatus(false);
}

function renderSearchResults(results) {
    const section = document.getElementById('search-results-section');
    const container = document.getElementById('fund-search-results');
    if (!results.length) {
        section.style.display = 'none';
        return;
    }
    container.innerHTML = results.map(f =>
        `<div class="fund-card" onclick="loadFund('${f.scheme_code}')">
            <div class="fund-house">${f.fund_house || ''}</div>
            <div class="fund-name">${f.scheme_name || ''}</div>
            <div class="fund-category">${f.scheme_category || ''}</div>
        </div>`
    ).join('');
    section.style.display = 'block';
    document.getElementById('fund-list-section').scrollIntoView({ behavior: 'smooth' });
}

// ── Fund Detail ──────────────────────────────────────────────────────────────

async function loadFund(schemeCode) {
    setMFStatus(true, 'Loading fund data...');
    try {
        const resp = await fetch(`/api/mf/${schemeCode}`);
        const data = await resp.json();
        if (data.error) { alert(data.error); return; }
        currentFund = data;
        renderFundDetail(data);
    } catch (e) {
        console.error(e);
    }
    setMFStatus(false);
}

function renderFundDetail(fund) {
    // Show detail, hide list
    document.getElementById('fund-list-section').style.display = 'none';
    document.getElementById('fund-detail').style.display = 'block';

    document.getElementById('fund-title').textContent = fund.scheme_name;
    document.getElementById('fund-category').textContent =
        `${fund.scheme_category || ''} · ${fund.fund_house || ''}`;

    // Metrics
    const metrics = [
        ['Latest NAV',   `₹${fund.nav.toFixed(4)}`],
        ['NAV Date',     fund.nav_date],
        ['Fund House',   fund.fund_house],
        ['Category',     fund.scheme_category],
        ['Type',         fund.scheme_type],
        ['1M Return',    fund.return_1m != null ? `${fund.return_1m >= 0 ? '+' : ''}${fund.return_1m}%` : 'N/A'],
        ['6M Return',    fund.return_6m != null ? `${fund.return_6m >= 0 ? '+' : ''}${fund.return_6m}%` : 'N/A'],
        ['1Y Return',    fund.return_1y != null ? `${fund.return_1y >= 0 ? '+' : ''}${fund.return_1y}%` : 'N/A'],
    ];
    const retCls = (val) => val && val.startsWith('+') ? 'ret-positive' : val && val.startsWith('-') ? 'ret-negative' : '';
    document.getElementById('fund-metrics').innerHTML = metrics.map(([label, val]) =>
        `<div class="metric-item">
            <span class="metric-label">${label}</span>
            <span class="metric-value ${retCls(val)}">${val}</span>
        </div>`
    ).join('');

    // NAV Chart
    renderNAVChart(fund.nav_history);

    // Update units info
    updateMFUnitsInfo();
    document.getElementById('mf-trade-result').innerHTML = '';
}

function closeFundDetail() {
    document.getElementById('fund-detail').style.display = 'none';
    document.getElementById('fund-list-section').style.display = 'block';
    currentFund = null;
    if (navChart) { navChart.destroy(); navChart = null; }
}

function renderNAVChart(history) {
    if (navChart) { navChart.destroy(); navChart = null; }
    if (!history || !history.length) return;

    const ctx = document.getElementById('nav-chart');
    navChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: history.map(h => h.date),
            datasets: [{
                label: 'NAV',
                data: history.map(h => h.nav),
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88,166,255,0.08)',
                fill: true,
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.1,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { display: true, ticks: { maxTicksLimit: 8, color: '#8b949e' }, grid: { color: '#21262d' } },
                y: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
            }
        }
    });
}

// ── Paper Trading ────────────────────────────────────────────────────────────

function setMFAmount(amt) {
    document.getElementById('mf-amount').value = amt;
    updateMFUnitsInfo();
}

document.getElementById('mf-amount').addEventListener('input', updateMFUnitsInfo);

function updateMFUnitsInfo() {
    if (!currentFund) return;
    const amount = parseFloat(document.getElementById('mf-amount').value) || 0;
    const nav = currentFund.nav;
    const units = Math.floor(amount / nav);
    const actual = units * nav;
    const el = document.getElementById('mf-units-info');
    el.innerHTML = amount > 0 && nav > 0
        ? `<span>₹${amount.toLocaleString()} ÷ ₹${nav.toFixed(4)} NAV = <strong>${units} units</strong></span>
           <span>Actual: <strong>₹${actual.toLocaleString(undefined, {maximumFractionDigits:2})}</strong></span>`
        : '';
}

async function buyFund() {
    if (!currentFund) return;
    const amount = parseFloat(document.getElementById('mf-amount').value) || 0;
    if (amount <= 0) { alert('Enter an amount'); return; }

    try {
        const resp = await fetch('/api/mf/buy', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ scheme_code: currentFund.scheme_code, amount })
        });
        const data = await resp.json();
        const resultEl = document.getElementById('mf-trade-result');
        if (data.order && data.order.status === 'EXECUTED') {
            resultEl.innerHTML = `<span style="color:var(--green)">
                Invested ₹${(data.units * data.nav).toLocaleString(undefined, {maximumFractionDigits:2})}
                → ${data.units} units at NAV ₹${data.nav.toFixed(4)} (${data.nav_date})
            </span>`;
        } else {
            resultEl.innerHTML = `<span style="color:var(--red)">${data.error || data.order?.reason || 'Investment failed'}</span>`;
        }
    } catch (e) {
        document.getElementById('mf-trade-result').innerHTML =
            `<span style="color:var(--red)">Error: ${e.message}</span>`;
    }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function setMFStatus(show, msg = '') {
    const el = document.getElementById('mf-status');
    el.style.display = show ? 'flex' : 'none';
    if (msg) document.getElementById('mf-status-text').textContent = msg;
}

// Close dropdown on outside click
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-wrap')) hideMFDropdown();
});

// Init
initFundsPage();
