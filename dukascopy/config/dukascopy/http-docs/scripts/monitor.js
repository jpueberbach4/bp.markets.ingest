async function queryDrift() {
    const symbolSelect = document.getElementById('symbolSelect');
    const tfSelect = document.getElementById('tfSelect');
    const statusDiv = document.getElementById('drift-indicator');

    if (!symbolSelect || !tfSelect || !statusDiv) return;
    
    if (!symbolSelect.value) {
        setTimeout(queryDrift, 500); 
        return;
    }

    const symbol = symbolSelect.value;
    const timeframe = tfSelect.value;
    
    const timestamp = Date.now() - (86400000 * 5); // weekend and holiday safety

    const url = `/ohlcv/1.1/select/${symbol},${timeframe}[drift()]/after/${timestamp}/output/JSON?limit=1&subformat=3&order=desc`;

    try {
        statusDiv.style.opacity = "0.5";
        
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        
        if (data.result && data.result.drift && data.result.drift.length > 0) {
            const driftValue = data.result.drift[0];
            statusDiv.innerText = `Drift: ${driftValue}m`;
            
            if (driftValue > 5) {
                statusDiv.style.color = '#ef5350'; 
                statusDiv.style.fontWeight = '900';
            } else if (driftValue > 1) {
                statusDiv.style.color = '#db991f'; 
                statusDiv.style.fontWeight = '700';
            } else {
                statusDiv.style.color = '#26a69a';
                statusDiv.style.fontWeight = 'bold';
            }
        } else {
            statusDiv.innerText = "Drift: --";
            statusDiv.style.color = 'inherit';
        }
        
    } catch (error) {
        console.warn("Drift Query Failed:", error);
        statusDiv.innerText = "Drift: ERR";
        statusDiv.style.color = '#ffa726';
    } finally {
        statusDiv.style.opacity = "1"; // Restore opacity
    }
}


function initDriftMonitor() {
    const now = new Date();
    let msToNext40 = (40 - now.getSeconds()) * 1000 - now.getMilliseconds();
    if (msToNext40 < 0) msToNext40 += 60000;
    setTimeout(() => {
        queryDrift();
        setInterval(queryDrift, 30000); // Lock to 30s cycle
    }, msToNext40);

    const symSelect = document.getElementById('symbolSelect');
    const tfSelect = document.getElementById('tfSelect');

    if (symSelect) symSelect.addEventListener('change', () => queryDrift());
    if (tfSelect) tfSelect.addEventListener('change', () => queryDrift());
    setTimeout(queryDrift, 1000);
}

initDriftMonitor();