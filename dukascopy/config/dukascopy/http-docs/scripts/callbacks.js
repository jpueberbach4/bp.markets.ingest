    const MS_PER_DAY = 24 * 60 * 60 * 1000;
    
    window.__callbackList = (res) => {
        symbolData = res.result;
        const sel = document.getElementById('symbolSelect');
        sel.innerHTML = Object.keys(symbolData).sort().map(s => `<option value="${s}">${s}</option>`).join('');
        updateTimeframeOptions();
        resetAndLoad(true);
    };

    window.__callbackIndicators = (res) => {
        indicatorMeta = res.result;
        document.getElementById('indicatorSelect').innerHTML = Object.keys(indicatorMeta).map(i => `<option value="${i}">${i.toUpperCase()}</option>`).join('');
        renderParams();
    };

    window.__callbackData = function(response) {
        isFetching = false;
        document.getElementById('loader').style.display = 'none';
        
        if (response.result && response.result.time && response.result.time.length > 0) {
            gapRetryCount = 0;
            const res = response.result;
            const cols = response.columns;

            const incoming = res.time.map((t, i) => {
                const item = {
                    time: t / 1000,
                    open: res.open[i], high: res.high[i], low: res.low[i], close: res.close[i],
                    value: res.volume[i],
                    indicators: {}
                };
                cols.forEach((col, idx) => {
                    if (idx > 5) item.indicators[col] = res[col][i];
                });
                return item;
            });

            const timeScale = mainChart.timeScale();
            const logicalRange = timeScale.getVisibleLogicalRange();

            let combined = [...masterData, ...incoming];
            const uniqueMap = new Map();
            combined.forEach(d => uniqueMap.set(d.time, d));
            const newData = Array.from(uniqueMap.values()).sort((a, b) => a.time - b.time);

            const lastOldTime = masterData.length > 0 ? masterData[masterData.length - 1].time : null;
            const addedToLeft = newData.findIndex(d => d.time === (masterData[0] ? masterData[0].time : null));
            const countAddedLeft = (addedToLeft === -1 || masterData.length === 0) ? 0 : addedToLeft;

            const oldLastIndex = lastOldTime ? newData.findIndex(d => d.time === lastOldTime) : -1;
            const countAddedRight = (oldLastIndex === -1) ? 0 : (newData.length - 1 - oldLastIndex);

            masterData = newData;

            console.log(requestDirection)

            if (masterData.length > bufferLimit) {
                
                if (requestDirection === 'future' || requestDirection === 'initial') {
                    masterData = masterData.slice(-bufferLimit);
                } 
                else if (requestDirection === 'history') {
                    masterData = masterData.slice(0, Math.max(bufferLimit, logicalRange.to + 100));
                }
            }

            updateChartUI(cols, requestDirection);

            if (window.anchorTime) {
                /* reset to anchor */
                const timeScale = mainChart.timeScale();
                const newLeftIndex = masterData.findIndex(d => d.time === window.anchorTime);
                console.log('anchoring: ' + window.anchorTime)
                if (newLeftIndex !== -1) {
                    timeScale.setVisibleLogicalRange({
                        from: newLeftIndex,
                        to: newLeftIndex + (window.savedWidth || 50)
                    });
                }
                window.anchorTime = null;
                window.savedWidth = null;
            }

            if (logicalRange !== null) {
                if (requestDirection === 'history' && countAddedLeft > 0) {
                    timeScale.setVisibleLogicalRange({ 
                        from: logicalRange.from + countAddedLeft, 
                        to: logicalRange.to + countAddedLeft 
                    });
                } 
            }

        } else if (gapRetryCount < maxGapRetries) {
            gapRetryCount++;
            const currentTs = requestDirection === 'history' ? parseInt(response.options.until) : parseInt(response.options.after);
            const nextTs = requestDirection === 'history' ? currentTs - MS_PER_DAY : currentTs + MS_PER_DAY;
            loadData(requestDirection, nextTs);
        }
    };