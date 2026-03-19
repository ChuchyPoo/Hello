// Trading page logic

async function loadPortfolio() {
    try {
        const [posResp, journalResp] = await Promise.all([
            fetch('/api/positions'),
            fetch('/api/journal'),
        ]);
        const positions = await posResp.json();
        const journal = await journalResp.json();

        renderPositions(positions.positions || []);
        renderJournal(journal.journal || []);
        renderSummary(positions.summary || {});
    } catch (e) {
        console.error('Failed to load portfolio:', e);
    }
}

function renderSummary(summary) {
    document.getElementById('balance').textContent = `₹${(summary.balance || 100000).toLocaleString()}`;
    document.getElementById('invested').textContent = `₹${(summary.invested || 0).toLocaleString()}`;
    document.getElementById('current-value').textContent = `₹${(summary.current_value || 0).toLocaleString()}`;

    const pnl = summary.total_pnl || 0;
    const pnlEl = document.getElementById('total-pnl');
    pnlEl.textContent = `${pnl >= 0 ? '+' : ''}₹${pnl.toLocaleString()} (${(summary.total_pnl_pct || 0).toFixed(1)}%)`;
    pnlEl.style.color = pnl >= 0 ? 'var(--green)' : 'var(--red)';

    document.getElementById('open-count').textContent = summary.open_positions || 0;
    const modeEl = document.getElementById('trade-mode');
    modeEl.textContent = (summary.broker || 'paper').toUpperCase();
    modeEl.className = `summary-value mode-${summary.broker === 'paper' ? 'paper' : 'live'}`;
}

function formatTicker(ticker) {
    if (ticker.startsWith('MF:')) return '📊 ' + ticker.replace('MF:', 'Fund #');
    return ticker.replace(/\.(NS|BO|L|DE|T|HK|AX|SI)$/, '');
}

function formatSellButton(ticker) {
    if (ticker.startsWith('MF:')) {
        const sc = ticker.replace('MF:', '');
        return `<button class="btn btn-sell btn-sm" onclick="sellMFPosition('${sc}')">REDEEM</button>`;
    }
    return `<button class="btn btn-sell btn-sm" onclick="sellPosition('${ticker}')">SELL</button>`;
}

function renderPositions(positions) {
    const tbody = document.getElementById('positions-tbody');
    if (!positions.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="empty-msg">No open positions</td></tr>';
        return;
    }
    tbody.innerHTML = positions.map(p => {
        const pnlClass = p.pnl >= 0 ? 'ret-positive' : 'ret-negative';
        const isMF = p.ticker.startsWith('MF:');
        const priceLabel = isMF ? 'NAV' : 'Price';
        const qtyLabel = isMF ? 'units' : 'shares';
        return `
        <tr>
            <td><strong>${formatTicker(p.ticker)}</strong></td>
            <td>${p.quantity} <span style="font-size:11px;color:var(--text-muted)">${qtyLabel}</span></td>
            <td>₹${p.entry_price.toFixed(isMF ? 4 : 2)}</td>
            <td>₹${p.current_price.toFixed(isMF ? 4 : 2)}</td>
            <td class="${pnlClass}">${p.pnl >= 0 ? '+' : ''}₹${p.pnl.toFixed(2)}</td>
            <td class="${pnlClass}">${p.pnl_pct >= 0 ? '+' : ''}${p.pnl_pct.toFixed(1)}%</td>
            <td>${isMF ? '—' : '₹' + p.stop_loss.toFixed(2)}</td>
            <td>${isMF ? '—' : '₹' + p.take_profit.toFixed(2)}</td>
            <td>${formatSellButton(p.ticker)}</td>
        </tr>`;
    }).join('');
}

function renderJournal(journal) {
    const tbody = document.getElementById('journal-tbody');
    if (!journal.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-msg">No trades yet</td></tr>';
        return;
    }
    // Show newest first
    const sorted = [...journal].reverse();
    tbody.innerHTML = sorted.map(t => {
        const actionClass = t.action === 'BUY' ? 'ret-positive' : 'ret-negative';
        const statusClass = t.status === 'EXECUTED' ? 'ret-positive' : 'ret-negative';
        const isMF = (t.ticker || '').startsWith('MF:');
        const displayTicker = formatTicker(t.ticker || '');
        const actionLabel = isMF ? (t.action === 'BUY' ? 'INVEST' : 'REDEEM') : t.action;
        return `
        <tr>
            <td>${new Date(t.timestamp).toLocaleString()}</td>
            <td><strong>${displayTicker}</strong></td>
            <td class="${actionClass}">${actionLabel}</td>
            <td>${t.quantity} ${isMF ? 'units' : ''}</td>
            <td>₹${(t.price || 0).toFixed(isMF ? 4 : 2)}</td>
            <td class="${statusClass}">${t.status}</td>
            <td>${t.reason || ''}</td>
        </tr>`;
    }).join('');
}

async function sellPosition(ticker) {
    try {
        const resp = await fetch('/api/trade', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ticker, action: 'SELL'})
        });
        await resp.json();
        loadPortfolio();
    } catch (e) {
        console.error('Sell failed:', e);
    }
}

async function sellMFPosition(schemeCode) {
    try {
        const resp = await fetch('/api/mf/sell', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({scheme_code: schemeCode})
        });
        await resp.json();
        loadPortfolio();
    } catch (e) {
        console.error('MF redeem failed:', e);
    }
}

async function resetPortfolio() {
    if (!confirm('Reset paper portfolio to ₹1,00,000? This will clear all positions and trades.')) return;
    try {
        await fetch('/api/portfolio/reset', {method: 'POST'});
        loadPortfolio();
    } catch (e) {
        console.error('Reset failed:', e);
    }
}

// SSE handler
window.handleSSE = function(data) {
    if (data.type === 'trade_update') {
        loadPortfolio();
    }
};

// Load on page ready
loadPortfolio();
