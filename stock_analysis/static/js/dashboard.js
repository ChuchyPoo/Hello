// Dashboard logic

let stockData = [];

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
        scanText.textContent = `${stockData.length} stocks found`;
    } catch (e) {
        scanText.textContent = 'Scan failed: ' + e.message;
    }
    btn.disabled = false;
    setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
}

function renderTable(data) {
    const tbody = document.getElementById('stock-tbody');
    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-msg">No results found</td></tr>';
        return;
    }
    tbody.innerHTML = data.map(s => {
        const sigClass = `signal-${s.signal.toLowerCase()}`;
        const badge = `<span class="signal-badge ${sigClass}">${s.signal}</span>`;
        const macdDir = s.indicators.macd_hist > 0 ? '+' : '';
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
            <td>${(s.notes || []).join(', ')}</td>
        </tr>`;
    }).join('');
}

// Sorting
let sortDir = {};
function sortTable(col) {
    const key = col;
    sortDir[key] = !sortDir[key];
    const dir = sortDir[key] ? 1 : -1;

    const fields = ['ticker','name','last_price','signal','confidence','score','rsi','macd_hist'];
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
        return (va - vb) * dir;
    });
    renderTable(stockData);
}

// SSE handler
window.handleSSE = function(data) {
    if (data.type === 'scan_progress') {
        const scanText = document.getElementById('scan-text');
        if (scanText) scanText.textContent = data.message;
    }
};
