document.addEventListener('DOMContentLoaded', () => {
    /* main entry point */
    initCharts();
    const s1 = document.createElement('script'); s1.src = "/ohlcv/1.1/list/symbols/output/JSONP?callback=__callbackList"; document.body.appendChild(s1);
    const s2 = document.createElement('script'); s2.src = "/ohlcv/1.1/list/indicators/output/JSONP?callback=__callbackIndicators"; document.body.appendChild(s2);
});

document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('calendarModal');
    const btn = document.getElementById('calendarBtn');
    const close = document.getElementById('closeModal');
    const okBtn = document.getElementById('calendarOk');
    const dateInput = document.getElementById('calendarInput');
    const themeToggle = document.getElementById('themeToggle');

    btn.onclick = () => modal.style.display = 'flex';
    close.onclick = () => modal.style.display = 'none';
    window.onclick = (e) => { if (e.target == modal) modal.style.display = 'none'; };

    themeToggle.onclick = () => {
        isDark = !isDark;
        document.body.classList.toggle('dark-theme', isDark);
        themeToggle.innerText = isDark ? "☀️ Light Mode" : "🌙 Dark Mode";

        const themeColors = isDark ? {
            back: '#131722',
            text: '#d1d4dc',
            grid: '#2a2e39'
        } : {
            back: '#ffffff',
            text: '#131722',
            grid: '#f0f3fa'
        };

        mainChart.applyOptions({
            layout: { background: { color: themeColors.back }, textColor: themeColors.text },
            grid: {
                vertLines: { color: themeColors.grid },
                horzLines: { color: themeColors.grid },
            },
            timeScale: { borderColor: themeColors.grid }
        });
        Object.values(panelCharts).forEach(p => {
            p.chart.applyOptions({
                layout: { background: { color: themeColors.back }, textColor: themeColors.text },
                grid: {
                    vertLines: { color: themeColors.grid },
                    horzLines: { color: themeColors.grid },
                }
            });
        });
    };

    okBtn.onclick = () => {
        const val = dateInput.value;
        if (!val) return;

        const timeScale = mainChart.timeScale();
        const range = timeScale.getVisibleLogicalRange();
        const jumpBarCount = range ? Math.round(range.to - range.from) : 1000;

        const [year, month, day] = val.split('-').map(Number);
        modal.style.display = 'none';
        const referenceTs = Date.UTC(year, month - 1, day);

        masterData = [];
        candleSeries.setData([]);
        volumeSeries.setData([]);
        Object.values(overlaySeriesMap).forEach(s => mainChart.removeSeries(s));
        overlaySeriesMap = {};
        Object.values(panelCharts).forEach(p => p.chart.remove());
        panelCharts = {};
        document.getElementById('panel-container').innerHTML = '';

        const jumpToStart = () => {
            const newRange = timeScale.getVisibleLogicalRange();
            if (newRange && masterData.length > 0) {
                timeScale.setVisibleLogicalRange({
                    from: 0,
                    to: jumpBarCount
                });

                candleSeries.priceScale().applyOptions({
                    autoScale: true,
                });

                timeScale.unsubscribeVisibleLogicalRangeChange(jumpToStart);
            }
        };

        timeScale.subscribeVisibleLogicalRangeChange(jumpToStart);
        loadData("future", referenceTs, jumpBarCount);
    };


    document.addEventListener('keydown', (e) => {
        const timeScale = mainChart.timeScale();
        const visibleRange = timeScale.getVisibleLogicalRange();
        if (!visibleRange) return;

        const barsInView = visibleRange.to - visibleRange.from;

        if (e.key === 'PageUp') {
            e.preventDefault();
            timeScale.setVisibleLogicalRange({
                from: visibleRange.from - barsInView,
                to: visibleRange.to - barsInView
            });
        } else if (e.key === 'PageDown') {
            e.preventDefault();
            timeScale.setVisibleLogicalRange({
                from: visibleRange.from + barsInView,
                to: visibleRange.to + barsInView
            });
        } else if (e.key === 'End') {
            e.preventDefault();
            timeScale.scrollToRealTime();
        }
    });

});
