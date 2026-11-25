(function () {
    "use strict";

    if (typeof window.Chart === "undefined") {
        return;
    }

    var styles = getComputedStyle(document.documentElement);

    function token(name, fallback) {
        var value = styles.getPropertyValue(name).trim();
        return value || fallback;
    }

    var colors = {
        text: token("--text", "#1b2333"),
        muted: token("--muted", "#6b7690"),
        surface: token("--surface", "#ffffff"),
        grid: token("--border", "#e3e7f0"),
        series: token("--chart-series", "#3b5bdb"),
        seriesWash: token("--chart-series-wash", "rgba(59, 91, 219, 0.10)"),
        scope: token("--chart-scope", "#e8590c"),
        ideal: token("--chart-ideal", "#8a94ab"),
        committed: token("--chart-committed", "#c3cad8"),
        pending: token("--chart-pending", "#9aa5bd"),
        progress: token("--chart-progress", "#3b5bdb"),
        done: token("--chart-done", "#14804a")
    };

    Chart.defaults.font.family = '"Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = colors.muted;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.animation.duration = 350;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.legend.labels.color = colors.text;
    Chart.defaults.plugins.tooltip.backgroundColor = colors.text;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 6;
    Chart.defaults.plugins.tooltip.boxPadding = 4;
    Chart.defaults.plugins.tooltip.usePointStyle = true;

    function readData(id) {
        var element = document.getElementById(id);
        if (!element) {
            return null;
        }
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return null;
        }
    }

    function canvas(id) {
        return document.getElementById(id);
    }

    function countScales(titleText) {
        return {
            x: {
                grid: { display: false },
                border: { color: colors.grid },
                ticks: { maxRotation: 0, autoSkipPadding: 12 }
            },
            y: {
                beginAtZero: true,
                grid: { color: colors.grid, lineWidth: 1 },
                border: { display: false },
                ticks: { precision: 0 },
                title: { display: Boolean(titleText), text: titleText || "", color: colors.muted }
            }
        };
    }

    function lineDataset(label, data, color, options) {
        return Object.assign(
            {
                label: label,
                data: data,
                borderColor: color,
                backgroundColor: color,
                borderWidth: 2,
                borderCapStyle: "round",
                borderJoinStyle: "round",
                tension: 0,
                spanGaps: false,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointHitRadius: 12,
                pointBackgroundColor: color,
                pointBorderColor: colors.surface,
                pointBorderWidth: 2
            },
            options || {}
        );
    }

    function referenceDataset(label, data, color) {
        return lineDataset(label, data, color, {
            borderDash: [6, 4],
            pointRadius: 0,
            pointHoverRadius: 4,
            pointBorderWidth: 0
        });
    }

    function barDataset(label, data, color) {
        return {
            label: label,
            data: data,
            backgroundColor: color,
            hoverBackgroundColor: color,
            borderRadius: 4,
            borderSkipped: "start",
            maxBarThickness: 24,
            categoryPercentage: 0.7,
            barPercentage: 0.9
        };
    }

    function taskLabel(value) {
        var rounded = Math.round(value * 10) / 10;
        var text = String(rounded).replace(".", ",");
        return text + (rounded === 1 ? " tarefa" : " tarefas");
    }

    function taskTooltip(context) {
        if (context.parsed.y === null) {
            return null;
        }
        return context.dataset.label + ": " + taskLabel(context.parsed.y);
    }

    function drawBurndown() {
        var data = readData("burndown-data");
        var element = canvas("burndown-chart");
        if (!data || !element || !data.total) {
            return;
        }

        var views = {
            burndown: {
                axis: "Tarefas restantes",
                datasets: function () {
                    return [
                        referenceDataset("Ideal", data.ideal, colors.ideal),
                        lineDataset("Restante real", data.remaining, colors.series, {
                            fill: "origin",
                            backgroundColor: colors.seriesWash,
                            pointBackgroundColor: colors.series
                        })
                    ];
                }
            },
            burnup: {
                axis: "Tarefas concluídas (acumulado)",
                datasets: function () {
                    return [
                        lineDataset("Escopo", data.scope, colors.scope, { pointRadius: 0, pointHoverRadius: 4 }),
                        referenceDataset("Ideal acumulado", data.ideal_completed, colors.ideal),
                        lineDataset("Concluídas", data.completed, colors.series, {
                            fill: "origin",
                            backgroundColor: colors.seriesWash,
                            pointBackgroundColor: colors.series
                        })
                    ];
                }
            }
        };

        var chart = new Chart(element, {
            type: "line",
            data: { labels: data.labels, datasets: views.burndown.datasets() },
            options: {
                interaction: { mode: "index", intersect: false },
                scales: countScales(views.burndown.axis),
                plugins: {
                    legend: { position: "bottom", align: "start" },
                    tooltip: { callbacks: { label: taskTooltip } }
                }
            }
        });

        var buttons = document.querySelectorAll(".chart-toggle-btn");
        buttons.forEach(function (button) {
            button.addEventListener("click", function () {
                var view = views[button.dataset.view];
                if (!view) {
                    return;
                }
                buttons.forEach(function (other) {
                    var active = other === button;
                    other.classList.toggle("is-active", active);
                    other.setAttribute("aria-pressed", active ? "true" : "false");
                });
                chart.data.datasets = view.datasets();
                chart.options.scales.y.title.text = view.axis;
                element.setAttribute(
                    "aria-label",
                    button.dataset.view === "burnup"
                        ? "Gráfico de burnup: escopo, conclusões ideais acumuladas e conclusões reais acumuladas"
                        : "Gráfico de burndown: linha ideal comparada ao trabalho restante real"
                );
                chart.update();
            });
        });
    }

    function drawStatus() {
        var data = readData("status-data");
        var element = canvas("status-chart");
        if (!data || !element) {
            return;
        }
        var palette = { pending: colors.pending, in_progress: colors.progress, done: colors.done };
        var total = data.reduce(function (sum, item) { return sum + item.total; }, 0);
        if (!total) {
            return;
        }
        new Chart(element, {
            type: "doughnut",
            data: {
                labels: data.map(function (item) { return item.label; }),
                datasets: [{
                    data: data.map(function (item) { return item.total; }),
                    backgroundColor: data.map(function (item) { return palette[item.status] || colors.ideal; }),
                    borderColor: colors.surface,
                    borderWidth: 2,
                    hoverOffset: 4
                }]
            },
            options: {
                cutout: "64%",
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                var share = Math.round((context.parsed * 1000) / total) / 10;
                                return context.label + ": " + taskLabel(context.parsed) + " (" + String(share).replace(".", ",") + "%)";
                            }
                        }
                    }
                }
            }
        });
    }

    function drawFlow() {
        var data = readData("flow-data");
        if (!data) {
            return;
        }
        var hasData = data.created.some(Boolean) || data.completed.some(Boolean);
        if (!hasData) {
            return;
        }
        var throughputElement = canvas("throughput-chart");
        if (throughputElement) {
            new Chart(throughputElement, {
                type: "bar",
                data: { labels: data.labels, datasets: [barDataset("Concluídas", data.completed, colors.series)] },
                options: {
                    scales: countScales(""),
                    plugins: { legend: { display: false }, tooltip: { callbacks: { label: taskTooltip } } }
                }
            });
        }
        var flowElement = canvas("flow-chart");
        if (flowElement) {
            new Chart(flowElement, {
                type: "line",
                data: {
                    labels: data.labels,
                    datasets: [
                        lineDataset("Criadas", data.created, colors.scope),
                        lineDataset("Concluídas", data.completed, colors.series)
                    ]
                },
                options: {
                    interaction: { mode: "index", intersect: false },
                    scales: countScales(""),
                    plugins: {
                        legend: { position: "bottom", align: "start" },
                        tooltip: { callbacks: { label: taskTooltip } }
                    }
                }
            });
        }
    }

    function groupPercentage(width, groups, bars) {
        if (!width || !groups) {
            return 0.7;
        }
        return Math.min(0.7, (bars * 26) / (width / groups));
    }

    function fitGroups(chart, width) {
        var percentage = groupPercentage(width, chart.data.labels.length, chart.data.datasets.length);
        chart.data.datasets.forEach(function (dataset) {
            dataset.categoryPercentage = percentage;
            dataset.barPercentage = 0.92;
        });
    }

    function drawVelocity() {
        var data = readData("velocity-data");
        var element = canvas("velocity-chart");
        if (!data || !element || !data.labels.length) {
            return;
        }
        var chart = new Chart(element, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [
                    barDataset("Comprometidas", data.committed, colors.committed),
                    barDataset("Concluídas na janela", data.completed, colors.series)
                ]
            },
            options: {
                interaction: { mode: "index", intersect: false },
                scales: countScales(""),
                onResize: function (resized, size) {
                    fitGroups(resized, size.width);
                    resized.update("none");
                },
                plugins: {
                    legend: { position: "bottom", align: "start" },
                    tooltip: {
                        callbacks: {
                            title: function (items) {
                                var sprint = data.sprints[items[0].dataIndex];
                                var suffix = sprint.state === "active" ? " (em andamento)" : "";
                                return sprint.project + " · " + sprint.name + suffix;
                            },
                            label: taskTooltip
                        }
                    }
                }
            }
        });
        fitGroups(chart, chart.chartArea ? chart.chartArea.width : element.clientWidth);
        chart.update("none");
    }

    drawBurndown();
    drawStatus();
    drawFlow();
    drawVelocity();
})();
