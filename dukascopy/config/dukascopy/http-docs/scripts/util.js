
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        document.getElementById('short_message').innerHTML = 'Copied!'
    } catch (err) {
        document.getElementById('short_message').innerHTML = 'Failed'

    }
    setTimeout(() => {
        document.getElementById('short_message').innerHTML = '';
    }, 500)
}

function copyUrl() {
    let url = getDataUri('future', getVisibleTimestampLeft()*1000, 1000, "JSON");
    copyToClipboard(url);
}

function formatUnixToLiteral(unix) {
    const d = new Date(unix * 1000);
    return d.toISOString().replace('T', ' ').split('.')[0];
}

function getCurrentTimeframe(){
    const tfSelect = document.getElementById('tfSelect');
    return tfSelect.value;
}

function getCurrentSymbol(){
      const symSelect = document.getElementById('symbolSelect');
      return symSelect.value;
}

function getDataUri(direction, referenceTs, limit = 1000, type = "JSONP"){
    const sym = document.getElementById('symbolSelect').value;
    const tf = document.getElementById('tfSelect').value;
    if(!sym || !tf) return;
    
    const chainStr = chain.length ? `[${chain.map(i => `${i.name}(${i.params.join(',')})`).join(':')}]` : "";
    let url = `${location.protocol}//${location.hostname}:${location.port}/ohlcv/1.1/select/${sym},${tf}${chainStr}`;
    
    const fetchLimit = Math.min(limit, 5000);

    let callback = "";
    if (type == "JSONP") {
        callback = "&callback=__callbackData";
    }

    let params = `output/${type}?limit=${fetchLimit}${callback}&subformat=3`;

    if (direction === 'history') {
        url += `/until/${referenceTs || Date.now()}`;
        params += `&order=desc`;
    } else if (direction === 'future') {
        url += `/after/${referenceTs || (masterData.length > 0 ? masterData[masterData.length-1].time * 1000 : Date.now())}`;
        params += `&order=asc`;
    } else {
        if (referenceTs) {
            url += `/after/${referenceTs}`;
            params += `&order=asc`;
        } else {
            url += `/until/${Date.now()}`;
            params += `&order=desc`;
        }
    }
    url = `${url}/${params}`;
    return url;
}

function getVisibleTimestampLeft() {
    const timeScale = mainChart.timeScale();
    const logicalRange = timeScale.getVisibleLogicalRange();
    let referenceTs = masterData[0].time*1000;
    if (logicalRange){
        /* get first visiable candle timestamp */
        const firstVisibleIdx = Math.max(0, Math.floor(logicalRange.from));
        referenceTs = masterData[firstVisibleIdx].time;
    } 
    return referenceTs;    
}

function getVisibleNumberOfBars() {
    const timeScale = mainChart.timeScale();
    const logicalRange = timeScale.getVisibleLogicalRange();
    if (logicalRange){
        return logicalRange.to - logicalRange.from;
    } 
    return 1000;    
}

function getSeriesColor(col) {
    const palette = {
        'stoch_k': '#2962FF',    // Blue
        'stoch_d': '#FF6D00',    // Orange
        'signal': '#FF5252',     // Red
        'macd': '#2962FF',       // Blue
        'upper': '#787b86',      // Gray
        'lower': '#787b86',      // Gray
        'middle': '#FF9800',     // Amber
        'rsi': '#9c27b0',        // Purple
        'hist': '#26a69a',       // Teal
        'confidence': '#FFD600', // Orange
        'threshold': '#00FF00',   // Lime
        'relative-height': '#1B6E1B' //Deep Forest
    };
    const mainParts = col.split('__');
    const suffix = (mainParts.length > 1 ? mainParts[1] : col.split('_').shift()).toLowerCase();
    color = 0;
    if (palette[suffix]) { 
        color = palette[suffix];
    } else {
        let hash = 0;
        for (let i = 0; i < col.length; i++) {
            hash = col.charCodeAt(i) + ((hash << 5) - hash);
        }
        color = `hsl(${Math.abs(hash % 360)}, 80%, 50%)`;
    }
    return color;
}

function getTitleString(col) {
    const parts = col.split('_');
    const name = parts[0].toUpperCase();
    const params = parts.filter(p => !isNaN(p) && p !== "");
    const titleStr = params.length > 0 ? `${name} (${params.join(',')})` : name;
    return titleStr;
}


function loadData(direction, referenceTs, limit = 1000) {
    if (isFetching) return;
    const sym = document.getElementById('symbolSelect').value;
    const tf = document.getElementById('tfSelect').value;
    if(!sym || !tf) return;

    isFetching = true;
    requestDirection = direction;
    document.getElementById('loader').style.display = 'flex';

    let url = getDataUri(direction, referenceTs, limit = 1000);

    const s = document.createElement('script');
    s.src = url;
    document.body.appendChild(s);
}

function openExportModal() {
    const modal = document.getElementById('export-modal');
    const dateInput = document.getElementById('export-after');
    
    if (masterData.length > 0) {
        dateInput.value = formatUnixToLiteral(masterData[0].time);
    } else {
        dateInput.value = formatUnixToLiteral(Math.floor(Date.now() / 1000));
    }
    
    modal.style.display = 'flex';
}

function syncBufferLimit() {
    const container = document.getElementById('main-chart-container');
    const spacing = mainChart.timeScale().options().barSpacing || 6;
    const visibleBars = Math.ceil(container.offsetWidth / spacing);
    const target = Math.max(3000, visibleBars * 3); 

    if (Math.abs(target - bufferLimit) > 200) {
        bufferLimit = target;
    }
}

function runExportGetUrl() {
    const sym = document.getElementById('symbolSelect').value;
    let tf = document.getElementById('tfSelect').value;
    
    if (document.getElementById('export-skiplast').checked) tf += ':skiplast';
    const output = document.getElementById('export-mt4').checked ? 'CSV/MT4' : 'CSV';
    
    const after = document.getElementById('export-after').value.replace(/ /g, "+");
    const limit = document.getElementById('export-limit').value;
    const order = document.getElementById('export-order').value;
    const chainStr = chain.length ? `[${chain.map(i => `${i.name}(${i.params.join(',')})`).join(':')}]` : "";
    
    const exportUrl = `${location.protocol}//${location.host}/ohlcv/1.1/select/${sym},${tf}${chainStr}/after/${after}/output/${output}?limit=${limit}&order=${order}`;
    return exportUrl;
}


function runExportUrl(){
    exportUrl = runExportGetUrl();
    copyToClipboard(exportUrl);
}


function runExport() {
    exportUrl = runExportGetUrl();
    window.location.href = exportUrl;
}

