(() => {
    "use strict";

    const bootstrap = window.analyticsBootstrap;
    const svgNS = "http://www.w3.org/2000/svg";

    function svgElement(name, attributes = {}) {
        const element = document.createElementNS(svgNS, name);
        for (const [key, value] of Object.entries(attributes)) {
            element.setAttribute(key, String(value));
        }
        return element;
    }

    function renderChart(container, series, field, color) {
        container.replaceChildren();
        const width = 520;
        const height = 210;
        const padding = { top: 18, right: 12, bottom: 28, left: 35 };
        const chartWidth = width - padding.left - padding.right;
        const chartHeight = height - padding.top - padding.bottom;
        const values = series.map((point) => Number(point[field]) || 0);
        const maximum = Math.max(...values, field === "accuracy" ? 100 : 1);
        const svg = svgElement("svg", {
            viewBox: `0 0 ${width} ${height}`,
            role: "img",
            "aria-label": container.previousElementSibling?.textContent || "График",
        });

        for (let index = 0; index <= 4; index += 1) {
            const y = padding.top + chartHeight * index / 4;
            svg.appendChild(svgElement("line", {
                x1: padding.left, y1: y, x2: width - padding.right, y2: y,
                class: "chart-grid-line",
            }));
            const label = svgElement("text", {
                x: padding.left - 7, y: y + 3, class: "chart-label", "text-anchor": "end",
            });
            label.textContent = String(Math.round(maximum * (4 - index) / 4));
            svg.appendChild(label);
        }

        if (!series.length) {
            container.appendChild(svg);
            return;
        }
        const xFor = (index) => padding.left + (
            series.length === 1 ? chartWidth / 2 : chartWidth * index / (series.length - 1)
        );
        const yFor = (value) => padding.top + chartHeight * (1 - value / maximum);
        const points = values.map((value, index) => `${xFor(index)},${yFor(value)}`).join(" ");
        const area = `${padding.left},${padding.top + chartHeight} ${points} ${width - padding.right},${padding.top + chartHeight}`;
        svg.appendChild(svgElement("polygon", { points: area, fill: color, class: "chart-area" }));
        svg.appendChild(svgElement("polyline", { points, stroke: color, class: "chart-line" }));

        const labelEvery = Math.max(1, Math.ceil(series.length / 6));
        series.forEach((point, index) => {
            if (index % labelEvery === 0 || index === series.length - 1) {
                const label = svgElement("text", {
                    x: xFor(index), y: height - 6, class: "chart-label", "text-anchor": "middle",
                });
                label.textContent = point.label;
                svg.appendChild(label);
            }
            const dot = svgElement("circle", {
                cx: xFor(index), cy: yFor(values[index]), r: 3.5,
                fill: color, class: "chart-dot", tabindex: "0",
            });
            const title = svgElement("title");
            title.textContent = `${point.label}: ${values[index]}`;
            dot.appendChild(title);
            svg.appendChild(dot);
        });
        container.appendChild(svg);
    }

    document.querySelectorAll("[data-chart]").forEach((container) => {
        renderChart(
            container,
            bootstrap.daily,
            container.dataset.chart,
            container.dataset.color,
        );
    });

    const periodSelect = document.querySelector("[data-period-select]");
    const customDates = document.querySelectorAll(".custom-date");
    function updateCustomDates() {
        const visible = periodSelect?.value === "custom";
        customDates.forEach((field) => { field.hidden = !visible; });
    }
    periodSelect?.addEventListener("change", updateCustomDates);
    updateCustomDates();

    const dialog = document.querySelector("[data-detail-dialog]");
    const detailContent = document.querySelector("[data-detail-content]");
    document.querySelector("[data-dialog-close]")?.addEventListener("click", () => dialog.close());
    dialog?.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
    });

    function detailMarkup(item) {
        return `
            <h2></h2>
            <p class="detail-meta"></p>
            <div class="detail-metrics">
                <div><span>Пользователей</span><strong>${item.unique_users}</strong></div>
                <div><span>Ответов</span><strong>${item.answered}</strong></div>
                <div><span>Ошибок</span><strong>${item.wrong}</strong></div>
                <div><span>Пропусков</span><strong>${item.skips}</strong></div>
                <div><span>Точность</span><strong>${item.accuracy}%</strong></div>
                <div><span>Повторяли</span><strong>${item.repeat_users}</strong></div>
            </div>
            <div class="chart detail-chart" data-detail-chart></div>
        `.trim();
    }

    async function openItemDetail(itemId) {
        detailContent.innerHTML = "<p>Загрузка…</p>";
        dialog.showModal();
        const endpoint = bootstrap.itemUrl.replace("/0", `/${itemId}`);
        const query = new URLSearchParams(bootstrap.query);
        try {
            const response = await fetch(`${endpoint}?${query}`, {
                headers: { Accept: "application/json" },
            });
            if (!response.ok) throw new Error();
            const item = await response.json();
            detailContent.innerHTML = detailMarkup(item);
            detailContent.querySelector("h2").textContent = item.title;
            const type = item.type === "spelling" ? "Орфография" : "Паронимы";
            detailContent.querySelector(".detail-meta").textContent = [
                type, item.task ? `ЕГЭ ${item.task}` : null, item.category,
            ].filter(Boolean).join(" · ");
            const chart = detailContent.querySelector("[data-detail-chart]");
            renderChart(chart, item.daily, "cards", "#7c5cff");
        } catch {
            detailContent.innerHTML = "<p>Не удалось загрузить статистику задания.</p>";
        }
    }

    const exerciseRows = document.querySelector("[data-item-rows]");
    const exerciseTable = document.querySelector("[data-exercise-table]");
    const exerciseEmpty = document.querySelector("[data-exercise-empty]");
    const exerciseCount = document.querySelector("[data-exercise-count]");
    const exerciseSorts = document.querySelector("[data-exercise-sorts]");
    const searchForm = document.querySelector(".exercise-search");
    const searchInput = document.querySelector("#exercise-query");
    const searchReset = document.querySelector("[data-search-reset]");
    const searchStatus = document.querySelector("[data-search-status]");
    let searchTimer = null;
    let searchRequest = null;

    function appendMetricCell(row, label, value) {
        const cell = document.createElement("td");
        cell.dataset.label = label;
        cell.textContent = value;
        row.appendChild(cell);
    }

    function renderExercises(payload) {
        exerciseRows.replaceChildren();
        payload.items.forEach((item) => {
            const row = document.createElement("tr");
            const titleCell = document.createElement("td");
            titleCell.dataset.label = "Упражнение";
            const button = document.createElement("button");
            button.type = "button";
            button.className = "item-link";
            button.dataset.itemId = item.id;
            button.textContent = item.title;
            const metadata = document.createElement("small");
            metadata.textContent = `${item.category}${item.task ? ` · ЕГЭ ${item.task}` : ""}`;
            titleCell.append(button, metadata);
            row.appendChild(titleCell);
            appendMetricCell(row, "Тип", item.type === "spelling" ? "Орфография" : "Паронимы");
            appendMetricCell(row, "Ответы", item.answered);
            appendMetricCell(row, "Ошибки", item.wrong);
            appendMetricCell(row, "Пропуски", item.skips);
            appendMetricCell(row, "Точность", `${item.accuracy}%`);
            exerciseRows.appendChild(row);
        });
        const hasItems = payload.items.length > 0;
        exerciseTable.hidden = !hasItems;
        exerciseEmpty.hidden = hasItems;
        exerciseSorts.hidden = !hasItems;
        exerciseCount.textContent = `Показано ${payload.items.length} из ${payload.item_count}`;
    }

    function updateSearchLinks(params) {
        document.querySelectorAll("[data-exercise-sort]").forEach((link) => {
            const linkParams = new URLSearchParams(params);
            linkParams.set("exercise_sort", link.dataset.exerciseSort);
            link.href = `${window.location.pathname}?${linkParams}`;
        });
        const resetParams = new URLSearchParams(params);
        resetParams.delete("exercise_query");
        searchReset.href = `${window.location.pathname}?${resetParams}`;
    }

    async function searchExercises() {
        searchRequest?.abort();
        searchRequest = new AbortController();
        const params = new URLSearchParams(bootstrap.query);
        const value = searchInput.value.trim();
        if (value) params.set("exercise_query", value);
        else params.delete("exercise_query");
        searchReset.hidden = !value;
        searchStatus.textContent = "Ищем…";
        try {
            const response = await fetch(`${bootstrap.exerciseSearchUrl}?${params}`, {
                headers: { Accept: "application/json" },
                signal: searchRequest.signal,
            });
            if (!response.ok) throw new Error();
            renderExercises(await response.json());
            bootstrap.query = Object.fromEntries(params);
            updateSearchLinks(params);
            window.history.replaceState(null, "", `${window.location.pathname}?${params}`);
            searchStatus.textContent = "";
        } catch (error) {
            if (error.name !== "AbortError") {
                searchStatus.textContent = "Не удалось выполнить поиск";
            }
        }
    }

    function scheduleSearch() {
        clearTimeout(searchTimer);
        const value = searchInput.value.trim();
        const searchable = value.normalize("NFKC").match(/[\p{L}\p{N}]/gu) || [];
        if (value && searchable.length < 2) {
            searchRequest?.abort();
            searchReset.hidden = false;
            searchStatus.textContent = "Введите минимум 2 буквы или цифры";
            return;
        }
        searchStatus.textContent = value ? "Ищем…" : "";
        searchTimer = setTimeout(searchExercises, 350);
    }

    searchInput?.addEventListener("input", scheduleSearch);
    searchForm?.addEventListener("submit", (event) => {
        event.preventDefault();
        clearTimeout(searchTimer);
        searchExercises();
    });
    searchReset?.addEventListener("click", (event) => {
        event.preventDefault();
        searchInput.value = "";
        clearTimeout(searchTimer);
        searchExercises();
        searchInput.focus();
    });
    exerciseRows?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-item-id]");
        if (button) openItemDetail(button.dataset.itemId);
    });
})();
