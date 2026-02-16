    const MS_PER_DAY = 24 * 60 * 60 * 1000;

    const tooltip = document.createElement('div');
    tooltip.id = 'indicator-tooltip';
    document.body.appendChild(tooltip);

    let hoverTimer;    


    window.__callbackList = (res) => {
        if (res && res.status == "failure") {
            alert("There was a failure, check your service console: "+res.exception)
            return
        }
        symbolData = res.result;
        const sel = document.getElementById('symbolSelect');
        sel.innerHTML = Object.keys(symbolData).sort().map(s => `<option value="${s}">${s}</option>`).join('');
        updateTimeframeOptions();
        resetAndLoad(true);
    };

    window.__callbackIndicators = (res) => {
        if (res && res.status == "failure") {
            alert("Failure: " + res.exception);
            return;
        }
        indicatorMeta = res.result;

        const listContainer = document.getElementById('indicatorList');
        const display = document.getElementById('indicatorDisplay');
        const trigger = document.getElementById('indicatorTrigger');
        const hiddenInput = document.getElementById('indicatorSelect');
        
        listContainer.innerHTML = Object.keys(indicatorMeta).map(i => 
            `<div class="option-item" data-value="${i}">${i.toUpperCase()}</div>`
        ).join('');

        const firstKey = Object.keys(indicatorMeta)[0];
        if (firstKey) {
            selectItem(firstKey);
        }

        trigger.onclick = (e) => {
            e.stopPropagation(); 
            listContainer.classList.toggle('open');
            hideTooltip();
        };

        trigger.addEventListener('mouseenter', (e) => {
            const currentKey = hiddenInput.value;
            if (currentKey && indicatorMeta[currentKey]) {
                clearTimeout(hoverTimer);
                hoverTimer = setTimeout(() => showTooltip(e, indicatorMeta[currentKey]), 500);
            }
        });

        trigger.addEventListener('mouseleave', hideTooltip);

        window.addEventListener('click', () => {
            listContainer.classList.remove('open');
        });

        document.querySelectorAll('.option-item').forEach(item => {
            item.addEventListener('mouseenter', (e) => {
                const key = e.target.getAttribute('data-value');
                if (indicatorMeta[key]) {
                    clearTimeout(hoverTimer);
                    hoverTimer = setTimeout(() => showTooltip(e, indicatorMeta[key]), 500);
                }
            });

            item.addEventListener('mouseleave', hideTooltip);

            item.addEventListener('click', (e) => {
                e.stopPropagation();
                const key = e.target.getAttribute('data-value');
                selectItem(key);
                listContainer.classList.remove('open');
                hideTooltip();
            });
        });

        function selectItem(key) {
            display.innerText = key.toUpperCase();
            hiddenInput.value = key;
            renderParams();

            document.querySelectorAll('.option-item').forEach(el => {
                el.classList.remove('selected');
                if (el.getAttribute('data-value') === key) el.classList.add('selected');
            });
        }
    };

    function showTooltip(e, data) {
        const trigger = document.getElementById('indicatorTrigger');
        const rect = trigger.getBoundingClientRect();
        const formattedDescription = data.description.replace(/\n/g, '<br>');

        let metaHtml = '';
        if (data.meta) {
            metaHtml = Object.entries(data.meta)
                .map(([key, val]) => `<span class="meta-tag"><b>${key}</b>: ${val}</span>`)
                .join('');
        }

        tooltip.innerHTML = `
            <div style="margin-bottom:6px; font-weight:bold; color:white;">${data.name.toUpperCase()}</div>
            <div style="font-size:12px; line-height:1.4;">${formattedDescription}</div>
            <div style="margin-top:8px; font-size:11px; color:#777;">Warmup: ${data.warmup} bars</div>
            <div style="margin-top:4px;">${metaHtml}</div>
        `;

        tooltip.style.left = (rect.right + 10) + 'px';
        tooltip.style.top = rect.top + 'px';
        tooltip.style.display = 'block';
    }

    function hideTooltip() {
        clearTimeout(hoverTimer);
        tooltip.style.display = 'none';
    }

    window.__callbackIndicatorsXX = (res) => {
        if (res && res.status == "failure") {
            alert("There was a failure, check your service console: "+res.exception)
            return
        }
        indicatorMeta = res.result;
        document.getElementById('indicatorSelect').innerHTML = Object.keys(indicatorMeta).map(i => `<option value="${i}">${i.toUpperCase()}</option>`).join('');
        renderParams();
    };

    window.__callbackData = function(response) {
        isFetching = false;
        document.getElementById('loader').style.display = 'none';

        if (response && response.status == "failure") {
            alert("There was a failure, check your service console: "+response.exception)
            return
        }
        
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