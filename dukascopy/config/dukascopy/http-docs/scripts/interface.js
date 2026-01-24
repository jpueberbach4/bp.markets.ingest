let isDark = false;
let symbolData = {}; 
let indicatorMeta = {};
let chain = []; 
let masterData = []; 
let isFetching = false;
let requestDirection = null;

let hasMoreHistory = true;
let gapRetryCount = 0;
const maxGapRetries = 10;
let bufferLimit = 20; 

let rightPriceScaleWidth = 90;
let mainChart, candleSeries, volumeSeries;
let overlaySeriesMap = {}; 
let panelCharts = {};

/* main container */
const mainContainer = document.getElementById('main-chart-container');

function addToChain() {
    const indKey = document.getElementById('indicatorSelect').value;
    const meta = indicatorMeta[indKey];
    if (!meta) return;
    const params = meta.defaults ? Object.keys(meta.defaults).map(k => document.getElementById(`p_${k}`).value) : [];
    
    chain.push({ name: indKey, params, meta });
    updateChainUI();

    const timeScale = mainChart.timeScale();
    const visibleRange = timeScale.getVisibleLogicalRange();
    
    let referenceTime = Date.now();
    let visibleBarCount = 1000;

    if (visibleRange !== null && masterData.length > 0) {
        visibleBarCount = Math.ceil(visibleRange.to - visibleRange.from) + 10;
        const firstVisibleIdx = Math.max(0, Math.floor(visibleRange.from));
        if (masterData[firstVisibleIdx]) {
            referenceTime = masterData[firstVisibleIdx].time * 1000;
        } else {
            referenceTime = masterData[0].time * 1000;
        }
    }

    Object.values(overlaySeriesMap).forEach(s => mainChart.removeSeries(s));
    overlaySeriesMap = {};
    masterData = []; 
    loadData('initial', referenceTime, visibleBarCount); 
}

function clearOnUpdate() {
    masterData = [];
    candleSeries.setData([]);
    volumeSeries.setData([]);
    Object.values(overlaySeriesMap).forEach(s => mainChart.removeSeries(s));
    overlaySeriesMap = {};
    Object.values(panelCharts).forEach(p => p.chart.remove());
    panelCharts = {};
    document.getElementById('panel-container').innerHTML = '';
    candleSeries.priceScale().applyOptions({
        autoScale: true,
    });
}

function createPanel(id) {
    const container = document.getElementById('panel-container');
    const div = document.createElement('div');
    div.className = 'indicator-panel';
    div.style.height = '130px';
    div.style.width = '100%';
    div.style.marginTop = '5px';

    const titleDiv = document.createElement('div');
    titleDiv.className = 'panel-title';
    titleDiv.id = `title-${id}`;
    titleDiv.innerText = getTitleString(id.toUpperCase());
    div.appendChild(titleDiv);

    container.appendChild(div);
    
    const panelColors = isDark ? 
        { back: '#131722', text: '#d1d4dc', grid: '#2a2e39' } : 
        { back: '#ffffff', text: '#131722', grid: '#f0f3fa' };

    const chart = LightweightCharts.createChart(div, {
        width: div.clientWidth, height: 130,
        layout: { 
            background: { color: panelColors.back }, 
            textColor: panelColors.text, 
            attributionLogo: false 
        },
        grid: {
            vertLines: { color: panelColors.grid },
            horzLines: { color: panelColors.grid },
        },
        timeScale: { 
            visible: false,
            shiftVisibleRangeOnNewBar: false
        },
        rightPriceScale: { borderVisible: false, minimumWidth: rightPriceScaleWidth },
    });
    
    panelCharts[id] = { chart, series: {} };

    const currentRange = mainChart.timeScale().getVisibleLogicalRange();
    if (currentRange) {
        chart.timeScale().setVisibleLogicalRange(currentRange);
    }
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) {
            chart.timeScale().setVisibleLogicalRange(range);
        }
    });
}

function initCharts() {
    mainChart = LightweightCharts.createChart(mainContainer, {
        width: mainContainer.clientWidth,
        height: mainContainer.clientHeight,
        localization: { timeFormatter: (ts) => formatUnixToLiteral(ts) },
        layout: { background: { color: '#ffffff' }, textColor: '#131722', attributionLogo: false },
        timeScale: { timeVisible: true, borderColor: '#e0e3eb', shiftVisibleRangeOnNewBar: false },
        rightPriceScale: { 
            borderVisible: false, minimumWidth: rightPriceScaleWidth
        },
    });

    const resizeObserver = new ResizeObserver(entries => {
        if (entries.length === 0 || !entries[0].contentRect) return;
        const { width, height } = entries[0].contentRect;
        mainChart.applyOptions({ width, height });
        Object.values(panelCharts).forEach(p => p.chart.applyOptions({ width }));
    });

    resizeObserver.observe(mainContainer);

    candleSeries = mainChart.addSeries(LightweightCharts.CandlestickSeries, {
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350',
        priceFormat: { type: 'price', precision: 6, minMove: 0.000001 },
    });
    
    volumeSeries = mainChart.addSeries(LightweightCharts.HistogramSeries, {
        color: '#26a69a', priceFormat: { type: 'volume' }, priceScaleId: '',
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });

    mainChart.timeScale().applyOptions({
        shiftVisibleRangeOnNewBar: false,
    });
    const legend = document.getElementById('chart-legend');
    mainChart.subscribeCrosshairMove(param => {
        if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
            legend.style.display = 'none';
            return;
        }

        const data = param.seriesData.get(candleSeries);
        const volData = param.seriesData.get(volumeSeries);
        const masterPoint = masterData.find(d => d.time === param.time);
        if (!data || !masterPoint) return;

        legend.style.display = 'block';
        legend.style.left = (param.point.x + 165) + 'px';
        legend.style.top = (param.point.y + 65) + 'px';

        let html = `<div class="legend-ohlcv">`;
        html += `<div style="color: var(--text-gray); font-size: 10px; margin-bottom: 4px;">${formatUnixToLiteral(param.time)}</div>`;
        html += `O: ${data.open} H: ${data.high}<br>L: ${data.low} C: ${data.close}`;
        if (volData) html += `<br>Vol: ${volData.value.toLocaleString()}`;
        html += `</div>`;
        
        if (masterPoint.indicators) {
            Object.entries(masterPoint.indicators).forEach(([fullKey, val]) => {
                    const parts = fullKey.split('_');
                    const name = parts[0];
                    const suffix = parts[parts.length - 1];
                    
                    const params = parts.slice(1, -1).filter(p => !isNaN(p) && p !== "");
                    
                    const settings = params.length > 0 ? `(${params.join(',')})` : '';
                    const color = getSeriesColor(fullKey);

                    html += `<div class="legend-item">
                        <span>${name}${settings} ${suffix}</span>
                        <b style="color:${color}">${Number(val).toFixed(5)}</b>
                    </div>`;
            });
        }
        legend.innerHTML = html;
    });

    mainChart.timeScale().subscribeVisibleLogicalRangeChange(() => {
        if (isFetching || masterData.length === 0) return;
        const logicalRange = mainChart.timeScale().getVisibleLogicalRange();
        if (!logicalRange) return;

        syncBufferLimit();

        if (logicalRange.from < 10 && hasMoreHistory) {
            loadData('history', masterData[0].time * 1000);
        }
        if (logicalRange.to > masterData.length - 10) {
            loadData('future', (masterData[masterData.length - 1].time * 1000)+1);
        }
    });
    
    window.addEventListener('resize', syncBufferLimit);
    syncBufferLimit(); 

}

function removeFromChain(idx) {
    chain.splice(idx, 1);
    updateChainUI();
    resetAndLoad(true);
}

function renderParams() {
    const indKey = document.getElementById('indicatorSelect').value;
    const meta = indicatorMeta[indKey];
    const container = document.getElementById('params');
    container.innerHTML = (meta && meta.defaults) ? 
        Object.keys(meta.defaults).map(k => `<div style="margin-bottom:5px"><label style="font-size:9px;display:block;">${k}</label><input type="text" id="p_${k}" value="${meta.defaults[k]}" style="width:100%;box-sizing:border-box;"></div>`).join('') :
        '<span style="color:#999; font-size:11px">No parameters</span>';
}

function resetAndLoad(clear = false) {
    const s = document.createElement('script');
    s.src = `/ohlcv/1.1/list/indicators/output/JSONP?callback=__callbackIndicators&symbol=${getCurrentSymbol()}&timeframe=${getCurrentTimeframe()}`;
    document.body.appendChild(s);
    if (clear) {
        clearOnUpdate();
    } else{
        const range = mainChart.timeScale().getVisibleLogicalRange();  
        if (range && masterData.length > 0) {
            window.anchorTime = getVisibleTimestampLeft();               
            window.savedWidth = getVisibleNumberOfBars();
            masterData = [];
            candleSeries.setData([]);
            volumeSeries.setData([]);
            hasMoreHistory = true;
            gapRetryCount = 0;
            requestDirection = 'future';
            loadData('future', window.anchorTime * 1000);
            return;
        }
    }
    hasMoreHistory = true;
    gapRetryCount = 0;
    loadData('initial');
}

function updateChainUI() {
    document.getElementById('chain-list').innerHTML = chain.map((item, idx) => `
        <div class="indicator-tag">${item.name}(${item.params.join(',')})
            <span style="cursor:pointer; margin-left:8px; font-weight:bold;" onclick="removeFromChain(${idx})">✕</span>
        </div>`).join('');
}

function updateChartUI(cols = [], requestDirection) {
    candleSeries.setData(masterData.map(d => ({
        time: d.time, open: d.open, high: d.high, low: d.low, close: d.close
    })));
    
    volumeSeries.setData(masterData.map(d => ({
        time: d.time, value: d.value, 
        color: d.close >= d.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)'
    })));

    const statusEl = document.querySelector('#status-indicator');
    if (statusEl) {
        statusEl.innerText = `Buffer: ${masterData.length} bars`;
    }

    cols.forEach((col, idx) => {
        if (idx <= 5) return; 

        const rawName = col.split('_')[0]; 
        const meta = indicatorMeta[rawName];
        if (!meta) return;

        const mainParts = col.split('__');
        const basePart = mainParts[0]; 
        const displayTitle = (mainParts.length > 1) 
            ? mainParts[1] 
            : basePart.split('_')[0];

        const targetPanel = (meta.meta && meta.meta.panel === 1) ? 1 : 0;

        if (targetPanel === 0) {
            if (!overlaySeriesMap[col]) {
                overlaySeriesMap[col] = mainChart.addSeries(LightweightCharts.LineSeries, {
                    color: getSeriesColor(col),
                    lineWidth: 1,
                    title: displayTitle,
                    priceFormat: { type: 'price', precision: 6, minMove: 0.000001 },
                });
            }
            overlaySeriesMap[col].setData(masterData.map(d => ({ 
                time: d.time, value: d.indicators[col] 
            })).filter(v => v.value !== null));

        } else {
            const panelKey = basePart;
            if (!panelCharts[panelKey]) createPanel(panelKey);
            
            const pObj = panelCharts[panelKey];

            if (pObj.titleElement && !pObj.series[col]) {
                pObj.titleElement.innerText = params.length > 0 ? `${nameOnly} (${params.join(',')})` : nameOnly;
            }

            if (!pObj.series[col]) {
                pObj.series[col] = pObj.chart.addSeries(
                    col.includes('hist') ? LightweightCharts.HistogramSeries : LightweightCharts.LineSeries, 
                    {
                        color: getSeriesColor(col),
                        title: displayTitle,
                        lineWidth: 1,
                        priceFormat: { type: 'price', precision: 6, minMove: 0.000001 }
                    }
                );
            }

            const seriesData = masterData.map(d => {
                const item = { time: d.time, value: d.indicators[col] };
                if (col.includes('hist')) {
                    item.color = d.indicators[col] >= 0 ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)';
                }
                return item;
            }).filter(v => v.value !== null);

            pObj.series[col].setData(seriesData);
        }
    });
}

function updateTimeframeOptions() {
    const sym = document.getElementById('symbolSelect').value;
    const tfSelect = document.getElementById('tfSelect');
    const availableTfs = symbolData[sym] || [];
    const currentTf = tfSelect.value;

    tfSelect.innerHTML = availableTfs.map(tf => 
        `<option value="${tf}">${tf}</option>`
    ).join('');
    if (availableTfs.includes(currentTf)) {
        tfSelect.value = currentTf;
    } else {
        if (availableTfs.includes('1h')) {
            tfSelect.value = '1h';
        } else if (availableTfs.length > 0) {
            tfSelect.value = availableTfs[0];
        }
    }
}

