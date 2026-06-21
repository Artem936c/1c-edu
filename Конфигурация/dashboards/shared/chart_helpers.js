/* =========================================================================
   chart_helpers.js
   Обёртки над Chart.js (v4.x) для типовых диаграмм дашбордов.
   Зависит от Chart.js, загружаемого через CDN или встроенного.
   ========================================================================= */

(function (global) {
    'use strict';

    const PALETTE = [
        '#3b6dd1', '#6798c0', '#4f9d69', '#e3a857',
        '#b86db8', '#c8553d', '#7a8aa1', '#5a8f7e'
    ];

    const BASE_OPTIONS = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                labels: { font: { size: 12 }, color: '#2e3440' }
            },
            tooltip: {
                backgroundColor: 'rgba(46, 52, 64, 0.92)',
                titleFont: { size: 12, weight: 'bold' },
                bodyFont: { size: 12 },
                padding: 10,
                cornerRadius: 4
            }
        },
        scales: {
            x: {
                grid: { color: 'rgba(216, 222, 233, 0.5)' },
                ticks: { font: { size: 11 }, color: '#5c6b7a' }
            },
            y: {
                grid: { color: 'rgba(216, 222, 233, 0.5)' },
                ticks: { font: { size: 11 }, color: '#5c6b7a' }
            }
        }
    };

    /**
     * Глубокое слияние двух объектов (для опций Chart.js).
     */
    function deepMerge(target, source) {
        const result = Object.assign({}, target);
        for (const key in source) {
            if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                result[key] = deepMerge(target[key] || {}, source[key]);
            } else {
                result[key] = source[key];
            }
        }
        return result;
    }

    /**
     * Получить цвет из палитры по индексу (с зацикливанием).
     */
    function paletteColor(i) {
        return PALETTE[i % PALETTE.length];
    }

    /**
     * Линейный график с одной или несколькими сериями.
     *
     * @param {string} canvasId    — id canvas-элемента.
     * @param {string[]} labels    — подписи оси X.
     * @param {Object[]} series    — массив объектов {label, data, color?}.
     * @param {Object} [options]   — дополнительные опции Chart.js.
     */
    function createLineChart(canvasId, labels, series, options) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        const datasets = series.map((s, i) => ({
            label: s.label,
            data: s.data,
            borderColor: s.color || paletteColor(i),
            backgroundColor: (s.color || paletteColor(i)) + '22',
            borderWidth: 2,
            tension: 0.25,
            pointRadius: 3,
            pointHoverRadius: 5,
            fill: s.fill !== undefined ? s.fill : false
        }));

        return new Chart(ctx, {
            type: 'line',
            data: { labels: labels, datasets: datasets },
            options: deepMerge(BASE_OPTIONS, options || {})
        });
    }

    /**
     * Столбчатая диаграмма.
     */
    function createBarChart(canvasId, labels, series, options) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        const datasets = series.map((s, i) => ({
            label: s.label,
            data: s.data,
            backgroundColor: s.color || paletteColor(i),
            borderColor: s.color || paletteColor(i),
            borderWidth: 1
        }));

        return new Chart(ctx, {
            type: 'bar',
            data: { labels: labels, datasets: datasets },
            options: deepMerge(BASE_OPTIONS, options || {})
        });
    }

    /**
     * Стек-диаграмма.
     */
    function createStackedBarChart(canvasId, labels, series, options) {
        const stackedOpts = {
            scales: {
                x: { stacked: true },
                y: { stacked: true }
            }
        };
        return createBarChart(canvasId, labels, series, deepMerge(stackedOpts, options || {}));
    }

    /**
     * Круговая (pie) диаграмма.
     */
    function createPieChart(canvasId, labels, data, options) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        const colors = labels.map((_, i) => paletteColor(i));

        return new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderColor: '#ffffff',
                    borderWidth: 2
                }]
            },
            options: deepMerge({
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { font: { size: 12 } } }
                }
            }, options || {})
        });
    }

    /**
     * Боксплот «вручную» (без плагина) — рендеринг через Chart.js bar+error.
     * Принимает массив { label, q1, median, q3, min, max }.
     *
     * Простейшая реализация: рисует столбец от q1 до q3 с линией median.
     */
    function createBoxplot(canvasId, boxes, options) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return null;

        // Подготовка: основной столбец IQR (q1..q3) и «усы» min..max
        const labels = boxes.map(b => b.label);
        const iqrBase = boxes.map(b => b.q1);
        const iqrRange = boxes.map(b => Math.max(b.q3 - b.q1, 0.0001));
        const medians = boxes.map(b => b.median);
        const mins = boxes.map(b => b.min);
        const maxes = boxes.map(b => b.max);

        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'IQR (25%–75%)',
                        data: iqrRange,
                        base: iqrBase,
                        backgroundColor: paletteColor(1) + '55',
                        borderColor: paletteColor(1),
                        borderWidth: 1,
                        barPercentage: 0.5
                    },
                    {
                        label: 'Медиана',
                        type: 'scatter',
                        data: medians.map((m, i) => ({ x: labels[i], y: m })),
                        pointStyle: 'rectWide',
                        pointRadius: 8,
                        backgroundColor: paletteColor(0),
                        borderColor: paletteColor(0)
                    },
                    {
                        label: 'Min/Max',
                        type: 'scatter',
                        data: [].concat(
                            mins.map((m, i) => ({ x: labels[i], y: m })),
                            maxes.map((m, i) => ({ x: labels[i], y: m }))
                        ),
                        pointStyle: 'dash',
                        pointRadius: 6,
                        backgroundColor: paletteColor(5),
                        borderColor: paletteColor(5)
                    }
                ]
            },
            options: deepMerge(BASE_OPTIONS, options || {})
        });
    }

    /**
     * Тепловая карта (heatmap) на HTML-таблице с цветовым кодированием.
     * Рендерит в указанный контейнер (id), не использует Chart.js.
     *
     * @param {string} containerId — id блочного элемента.
     * @param {Object} data        — { rows: string[], cols: string[], values: number[][] | array of {row, col, value} }.
     * @param {Object} options     — { min?, max?, colorLow?, colorHigh? }.
     */
    function createHeatmap(containerId, data, options) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        options = options || {};
        const colorLow = options.colorLow || '#dde6f6';
        const colorHigh = options.colorHigh || '#3b6dd1';

        // Если values задан как массив объектов, преобразуем в матрицу
        let matrix;
        if (Array.isArray(data.values) && data.values.length > 0 &&
            typeof data.values[0] === 'object' && !Array.isArray(data.values[0])) {
            matrix = [];
            const rowIdx = {};
            data.rows.forEach((r, i) => { rowIdx[r] = i; });
            const colIdx = {};
            data.cols.forEach((c, i) => { colIdx[c] = i; });
            for (let i = 0; i < data.rows.length; i++) {
                matrix.push(new Array(data.cols.length).fill(null));
            }
            data.values.forEach(v => {
                const ri = rowIdx[v.row];
                const ci = colIdx[v.col];
                if (ri !== undefined && ci !== undefined) {
                    matrix[ri][ci] = v.value;
                }
            });
        } else {
            matrix = data.values;
        }

        // Вычислить min/max если не заданы
        let min = options.min, max = options.max;
        if (min === undefined || max === undefined) {
            const all = [];
            matrix.forEach(row => row.forEach(v => {
                if (v !== null && v !== undefined && !isNaN(v)) all.push(v);
            }));
            if (min === undefined) min = Math.min.apply(null, all);
            if (max === undefined) max = Math.max.apply(null, all);
        }

        function interpolate(v) {
            if (v === null || v === undefined || isNaN(v)) return '#f5f7fa';
            const t = Math.max(0, Math.min(1, (v - min) / (max - min || 1)));
            // Линейная интерполяция HEX
            const c1 = parseInt(colorLow.slice(1), 16);
            const c2 = parseInt(colorHigh.slice(1), 16);
            const r = Math.round(((c1 >> 16) & 0xff) * (1 - t) + ((c2 >> 16) & 0xff) * t);
            const g = Math.round(((c1 >> 8) & 0xff) * (1 - t) + ((c2 >> 8) & 0xff) * t);
            const b = Math.round((c1 & 0xff) * (1 - t) + (c2 & 0xff) * t);
            return 'rgb(' + r + ',' + g + ',' + b + ')';
        }

        // Сформировать HTML
        const html = ['<table class="heatmap-table"><thead><tr><th></th>'];
        data.cols.forEach(c => html.push('<th>' + escapeHtml(c) + '</th>'));
        html.push('</tr></thead><tbody>');
        data.rows.forEach((r, i) => {
            html.push('<tr><th class="row-header">' + escapeHtml(r) + '</th>');
            matrix[i].forEach(v => {
                const text = (v === null || v === undefined || isNaN(v))
                    ? '–'
                    : v.toFixed(2);
                html.push('<td style="background:' + interpolate(v) + '" title="' + text + '">' + text + '</td>');
            });
            html.push('</tr>');
        });
        html.push('</tbody></table>');
        container.innerHTML = html.join('');
    }

    /**
     * Простое экранирование HTML для безопасной вставки текста.
     */
    function escapeHtml(s) {
        if (s === null || s === undefined) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Форматирование даты ISO → ДД.ММ.ГГГГ для подписей.
     */
    function formatDate(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        const dd = String(d.getDate()).padStart(2, '0');
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const yyyy = d.getFullYear();
        return dd + '.' + mm + '.' + yyyy;
    }

    /**
     * Преобразование θ в подпись с одним знаком после запятой.
     */
    function formatTheta(v) {
        if (v === null || v === undefined || isNaN(v)) return '–';
        const sign = v >= 0 ? '+' : '';
        return sign + Number(v).toFixed(2) + ' лог.';
    }

    // Экспортируем публичный API
    global.ChartHelpers = {
        createLineChart: createLineChart,
        createBarChart: createBarChart,
        createStackedBarChart: createStackedBarChart,
        createPieChart: createPieChart,
        createBoxplot: createBoxplot,
        createHeatmap: createHeatmap,
        escapeHtml: escapeHtml,
        formatDate: formatDate,
        formatTheta: formatTheta,
        paletteColor: paletteColor,
        PALETTE: PALETTE
    };
})(typeof window !== 'undefined' ? window : this);
