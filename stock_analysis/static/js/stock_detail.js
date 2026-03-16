// Stock detail page logic

const ticker = document.getElementById('stock-detail').dataset.ticker;
let currentPrice = 0;

async function loadStockDetail() {
    try {
        const resp = await fetch(`/api/stock/${encodeURIComponent(ticker)}`);
        const data = await resp.json();
        if (data.error) {
            document.getElementById('detail-title').textContent = `${ticker} - Error`;
            return;
        }
        renderDetail(data);
    } catch (e) {
        console.error('Failed to load stock detail:', e);
    }
}

function renderDetail(data) {
    const s = data.signal;
    const sigClass = `signal-${s.signal.toLowerCase()}`;
    currentPrice = s.last_price;

    // Header
    document.getElementById('detail-title').textContent =
        `${s.ticker.replace('.NS','')} - ₹${s.last_price.toFixed(2)}`;
    const badge = document.getElementById('detail-signal');
    badge.textContent = `${s.signal} (${s.confidence.toFixed(1)}%)`;
    badge.className = `signal-badge ${sigClass}`;

    // Metrics
    const metricsEl = document.getElementById('metrics-grid');
    const metrics = [
        ['Price', `₹${s.last_price.toFixed(2)}`],
        ['Score', `${s.score > 0 ? '+' : ''}${s.score.toFixed(3)}`],
        ['RSI (14)', s.indicators.rsi.toFixed(1)],
        ['MACD Hist', s.indicators.macd_hist.toFixed(4)],
        ['Bollinger %B', s.indicators.pct_b.toFixed(3)],
        ['Stochastic %K', s.indicators.stoch_k.toFixed(1)],
        ['EMA 20', `₹${s.indicators.ema20.toFixed(2)}`],
        ['EMA 50', `₹${s.indicators.ema50.toFixed(2)}`],
        ['EMA 200', `₹${s.indicators.ema200.toFixed(2)}`],
        ['VWAP', `₹${s.indicators.vwap.toFixed(2)}`],
        ['Volume Ratio', `${s.indicators.vol_ratio.toFixed(2)}x`],
        ['ATR', s.indicators.atr.toFixed(4)],
    ];
    metricsEl.innerHTML = metrics.map(([label, val]) =>
        `<div class="metric-item">
            <span class="metric-label">${label}</span>
            <span class="metric-value">${val}</span>
        </div>`
    ).join('');

    // Fundamentals from Google Finance
    renderFundamentals(s.fundamentals || {});

    // Reasoning
    const reasonEl = document.getElementById('reasoning-list');
    reasonEl.innerHTML = (s.reasoning || []).map(r => {
        let cls = 'reason-item';
        if (r.includes('DECISION:')) cls += ' decision';
        else if (r.includes('+1.0]') || r.includes('+0.5]') || r.includes('+0.4]')) cls += ' bullish';
        else if (r.includes('-1.0]') || r.includes('-0.5]') || r.includes('-0.4]')) cls += ' bearish';
        return `<div class="${cls}">${r}</div>`;
    }).join('');

    // Historical matches
    renderHistorical(data.historical);

    // Charts
    if (s.price_data) renderPriceChart(s.price_data);
    if (s.indicators) renderRSIChart(s.price_data, s.indicators);
    renderSubScoreChart(s.sub_scores);

    // Update trade info
    updateTradeInfo();
}

function renderFundamentals(fund) {
    const grid = document.getElementById('fundamentals-grid');
    const srcBadge = document.getElementById('data-source');

    if (fund.data_source) {
        srcBadge.textContent = fund.data_source;
        srcBadge.style.display = 'inline';
    }

    const items = [];
    if (fund.pe_ratio) items.push(['P/E Ratio', fund.pe_ratio.toFixed(1)]);
    if (fund.dividend_yield) items.push(['Dividend Yield', `${fund.dividend_yield}%`]);
    if (fund.market_cap_str) items.push(['Market Cap', fund.market_cap_str]);
    if (fund.year_high) items.push(['52W High', `₹${fund.year_high.toLocaleString()}`]);
    if (fund.year_low) items.push(['52W Low', `₹${fund.year_low.toLocaleString()}`]);
    if (fund.prev_close) items.push(['Prev Close', `₹${fund.prev_close.toFixed(2)}`]);
    if (fund.change != null) {
        const cls = fund.change >= 0 ? 'ret-positive' : 'ret-negative';
        const sign = fund.change >= 0 ? '+' : '';
        items.push(['Day Change', `<span class="${cls}">${sign}₹${fund.change.toFixed(2)} (${sign}${fund.change_pct.toFixed(2)}%)</span>`]);
    }
    if (fund.volume_str) items.push(['Volume', fund.volume_str]);

    if (items.length === 0) {
        grid.innerHTML = '<div class="metric-item"><span class="metric-label">No fundamental data available</span></div>';
        return;
    }

    grid.innerHTML = items.map(([label, val]) =>
        `<div class="metric-item">
            <span class="metric-label">${label}</span>
            <span class="metric-value">${val}</span>
        </div>`
    ).join('');

    // Show description if available
    if (fund.description) {
        grid.innerHTML += `<div class="metric-item" style="grid-column: 1/-1">
            <span class="metric-label">About</span>
            <span class="metric-value" style="font-size:12px;font-weight:400;color:var(--text-secondary)">${fund.description}</span>
        </div>`;
    }
}

function setAmount(amt) {
    document.getElementById('trade-amount').value = amt;
    updateTradeInfo();
}

function updateTradeInfo() {
    const amount = parseFloat(document.getElementById('trade-amount').value) || 0;
    const infoEl = document.getElementById('trade-info');
    if (currentPrice > 0 && amount > 0) {
        const qty = Math.floor(amount / currentPrice);
        const actualCost = qty * currentPrice;
        infoEl.innerHTML = `
            <span>₹${amount.toLocaleString()} ÷ ₹${currentPrice.toFixed(2)} = <strong>${qty} shares</strong></span>
            <span>Actual cost: <strong>₹${actualCost.toLocaleString(undefined, {maximumFractionDigits:2})}</strong></span>
        `;
    } else {
        infoEl.innerHTML = '';
    }
}

// Update trade info when amount changes
document.getElementById('trade-amount').addEventListener('input', updateTradeInfo);

function renderHistorical(hist) {
    const summaryEl = document.getElementById('history-summary');
    const tbody = document.getElementById('match-tbody');

    if (!hist || !hist.matches || hist.matches.length === 0) {
        summaryEl.innerHTML = 'No similar historical patterns found in the available data. Try using a longer period (--period 1y or 2y).';
        tbody.innerHTML = '<tr><td colspan="7" class="empty-msg">No matches</td></tr>';
        return;
    }

    summaryEl.innerHTML = (hist.summary || '').replace(/\n/g, '<br>');

    tbody.innerHTML = hist.matches.map(m => {
        const retCell = (key) => {
            const val = m.forward_returns[key];
            if (val === null || val === undefined) return '<td>-</td>';
            const cls = val > 0 ? 'ret-positive' : 'ret-negative';
            return `<td class="${cls}">${val > 0 ? '+' : ''}${val.toFixed(1)}%</td>`;
        };
        return `
        <tr>
            <td>${m.match_date}</td>
            <td>${(m.similarity * 100).toFixed(1)}%</td>
            <td>${m.indicators.rsi.toFixed(1)}</td>
            ${retCell('1d')}
            ${retCell('5d')}
            ${retCell('10d')}
            ${retCell('20d')}
        </tr>`;
    }).join('');
}

function renderPriceChart(priceData) {
    const ctx = document.getElementById('price-chart');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: priceData.dates,
            datasets: [{
                label: 'Close Price',
                data: priceData.close,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88,166,255,0.1)',
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
                x: { display: true, ticks: { maxTicksLimit: 10, color: '#8b949e' }, grid: { color: '#21262d' } },
                y: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
            }
        }
    });
}

function renderRSIChart(priceData, indicators) {
    const ctx = document.getElementById('rsi-chart');
    const rsi = indicators.rsi;
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['RSI'],
            datasets: [{
                data: [rsi],
                backgroundColor: rsi < 30 ? '#3fb950' : rsi > 70 ? '#f85149' : '#d29922',
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: {
                legend: { display: false },
                annotation: {}
            },
            scales: {
                x: { min: 0, max: 100, ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
                y: { ticks: { color: '#8b949e' }, grid: { display: false } },
            }
        }
    });
}

function renderSubScoreChart(subScores) {
    if (!subScores) return;
    const ctx = document.getElementById('subscore-chart');
    const labels = Object.keys(subScores);
    const values = Object.values(subScores);
    const colors = values.map(v => v > 0 ? '#3fb950' : v < 0 ? '#f85149' : '#d29922');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.map(l => l.toUpperCase()),
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: { min: -1, max: 1, ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
                x: { ticks: { color: '#8b949e' }, grid: { display: false } },
            }
        }
    });
}

async function placeTrade(action) {
    const amount = parseFloat(document.getElementById('trade-amount').value) || 0;
    try {
        const resp = await fetch('/api/trade', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ticker, action, amount})
        });
        const data = await resp.json();
        const resultEl = document.getElementById('trade-result');
        if (data.order && data.order.status === 'EXECUTED') {
            const cost = data.order.quantity * data.order.price;
            resultEl.innerHTML = `<span style="color:var(--green)">Order ${data.order.status}: ${action} ${data.order.quantity} shares at ₹${data.order.price.toFixed(2)} (Total: ₹${cost.toLocaleString(undefined, {maximumFractionDigits:2})})</span>`;
        } else {
            resultEl.innerHTML = `<span style="color:var(--red)">${data.error || data.order?.reason || 'Trade failed'}</span>`;
        }
    } catch (e) {
        document.getElementById('trade-result').innerHTML = `<span style="color:var(--red)">Error: ${e.message}</span>`;
    }
}

// Load on page ready
loadStockDetail();
