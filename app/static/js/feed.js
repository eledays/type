(() => {
    "use strict";

    const ANIMATION_MS = 300;
    class FeedController {
        constructor(bootstrap, routes) {
            this.routes = routes;
            this.query = bootstrap.query || {};
            this.admin = Boolean(bootstrap.admin);
            this.isAnonymous = Boolean(bootstrap.anonymous);
            this.anonymousStarted = Boolean(bootstrap.anonymousStarted);
            this.strikeLevels = bootstrap.strikeLevels || [];
            this.backgroundPools = bootstrap.backgroundPools || {};
            this.backgroundQueues = new Map();
            this.lastBackgrounds = new Map();
            this.backgroundTheme = "dark";
            if (!Number.isInteger(bootstrap.batchSize) || bootstrap.batchSize < 1) {
                throw new Error("Некорректный размер пакета карточек");
            }
            this.batchSize = bootstrap.batchSize;
            this.refillAt = Math.max(1, this.batchSize - 1);
            this.queue = bootstrap.cards.slice(3);
            this.loading = null;
            this.locked = false;
            this.answerPending = false;
            this.pointer = null;
            this.longPressTimer = null;
            this.longPressOpened = false;
            this.answerLongPressTimer = null;
            this.suppressAnswerClick = false;

            this.feed = document.getElementById("feed");
            this.status = document.getElementById("feed-status");
            this.panels = [...document.querySelectorAll("[data-panel]")];
            this.panelOverlay = document.getElementById("panel-overlay");
            this.activePanel = null;
            this.panelTrigger = null;
            this.panelCloseTimer = null;
            this.closingPanel = null;
            this.closingTrigger = null;
            this.header = document.querySelector(".header");
            this.headerInfo = document.querySelector(".info-block");
            this.headerInfoTimer = null;
            this.info = document.getElementById("card-info");
            this.canvas = document.getElementById("effect-canvas");
            this.ctx = this.canvas.getContext("2d", {alpha: true});
            if (!this.isAnonymous && bootstrap.strike !== null && bootstrap.strike !== undefined) {
                this.headerInfo.dataset.strikeLevel = String(
                    Math.min(this.levelForStrike(bootstrap.strike), 4),
                );
            }
            const elements = [...this.feed.querySelectorAll(".card")];
            while (elements.length < 3) {
                const element = this.createCardElement();
                this.feed.appendChild(element);
                elements.push(element);
            }
            elements.slice(3).forEach((element) => element.remove());
            this.slots = elements.map((element, index) => ({
                element,
                card: bootstrap.cards[index] || null,
            }));
            this.current = this.slots[0];
            this.next = this.slots[1];
            this.buffered = this.slots[2];
            this.previous = null;

            this.slots.forEach((slot, index) => {
                if (slot.card && !slot.element.dataset.cardId) {
                    this.renderCard(slot, slot.card);
                } else if (slot.card) {
                    this.assignBackground(slot.element, this.backgroundTheme);
                }
                this.setPosition(
                    slot,
                    index === 0 ? "current" : index === 1 ? "next" : "buffered",
                    true,
                );
            });
            if (!this.next.card) this.setPosition(this.next, "buffered", true);
            this.updateCurrentMetadata();
            this.resizeCanvas();
            this.bindEvents();
        }

        async start() {
            if (!this.current.card) {
                await this.refill();
                this.assignInitialCards();
            }
            if (this.current.card) {
                this.status.classList.add("is-hidden");
                this.updateCurrentMetadata();
                void this.refill();
            }
        }

        createCardElement() {
            const article = document.createElement("article");
            article.className = "card is-buffered";
            return article;
        }

        assignInitialCards() {
            for (const slot of this.slots) {
                if (!slot.card && this.queue.length) {
                    this.renderCard(slot, this.queue.shift());
                }
            }
            this.current = this.slots[0];
            this.next = this.slots[1];
            this.buffered = this.slots[2];
            this.setPosition(this.current, "current", true);
            this.setPosition(this.next, this.next.card ? "next" : "buffered", true);
            this.setPosition(this.buffered, "buffered", true);
        }

        renderCard(slot, card) {
            const article = slot.element;
            slot.card = card;
            article.dataset.cardId = String(card.id);
            this.assignBackground(article, this.backgroundTheme);
            article.replaceChildren();

            const wordContainer = document.createElement("div");
            wordContainer.className = card.type === "paronym"
                ? "word-cont sentence-cont"
                : "word-cont";
            const word = document.createElement("p");
            word.className = "word";
            const parts = card.prompt.split(card.blank);
            parts.forEach((part, index) => {
                if (index) {
                    const blank = document.createElement("span");
                    blank.className = "missing-letter";
                    blank.setAttribute("aria-hidden", "true");
                    word.appendChild(blank);
                }
                const text = document.createElement("span");
                text.textContent = part;
                word.appendChild(text);
            });
            wordContainer.appendChild(word);
            article.appendChild(wordContainer);

            if (this.admin && card.type === "spelling") {
                const explanation = document.createElement("textarea");
                explanation.className = "explanation";
                explanation.setAttribute("aria-label", "Объяснение");
                explanation.value = card.explanation || "";
                explanation.dataset.initialValue = explanation.value;
                article.appendChild(explanation);
            }

            const answers = document.createElement("div");
            answers.className = "answers";
            for (const answer of card.answers) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = answer.length < 3 ? "answer" : "sentence-answer";
                button.dataset.answer = answer;
                button.textContent = answer;
                answers.appendChild(button);
            }
            article.appendChild(answers);
        }

        setPosition(slot, position, immediate = false) {
            if (!slot) return;
            const element = slot.element;
            if (immediate) element.classList.add("no-transition");
            element.classList.remove(
                "is-current", "is-previous", "is-next", "is-buffered", "is-above",
            );
            element.classList.add(`is-${position}`);
            if (immediate) {
                void element.offsetHeight;
                requestAnimationFrame(() => element.classList.remove("no-transition"));
            }
        }

        activeIds() {
            return [...new Set([
                ...this.slots.map((slot) => slot.card?.id),
                ...this.queue.map((card) => card.id),
            ].filter(Number.isInteger))];
        }

        async refill() {
            if (this.loading || this.queue.length >= this.refillAt) return this.loading;
            const params = new URLSearchParams();
            params.set("limit", String(this.batchSize));
            for (const [key, value] of Object.entries(this.query)) {
                if (value) params.set(key, value);
            }
            if (this.admin) params.set("admin", "1");
            const excluded = this.activeIds();
            if (excluded.length) params.set("exclude", excluded.join(","));

            this.loading = fetch(`${this.routes.cards}?${params}`, {
                headers: {Accept: "application/json"},
            }).then(async (response) => {
                const payload = await response.json();
                if (!response.ok) throw new Error(payload.message || "Не удалось загрузить задания");
                const known = new Set(this.activeIds());
                let fresh = payload.cards.filter((card) => !known.has(card.id));
                if (!fresh.length) fresh = payload.cards.slice(0, 1);
                this.queue.push(...fresh);
                return fresh;
            }).catch((error) => {
                if (!this.current.card) {
                    this.showStatus(error.message || "Не удалось загрузить задания");
                }
                return [];
            }).finally(() => {
                this.loading = null;
            });
            return this.loading;
        }

        async ensureNext() {
            if (this.next?.card) return true;
            if (this.buffered?.card) {
                this.next = this.buffered;
                this.buffered = null;
                this.setPosition(this.next, "next", true);
                return true;
            }
            if (!this.queue.length) await this.refill();
            if (!this.queue.length) {
                this.showStatus("Следующее задание пока не загрузилось. Попробуйте ещё раз.");
                return false;
            }
            const free = this.next || this.buffered || this.slots.find((slot) => (
                slot !== this.current && slot !== this.previous
            ));
            this.renderCard(free, this.queue.shift());
            this.next = free;
            if (this.buffered === free) this.buffered = null;
            this.setPosition(this.next, "next", true);
            return true;
        }

        async moveNext({recordSkip = true} = {}) {
            if (this.locked || (this.answerPending && recordSkip) || !this.current.card) return;
            this.locked = true;
            if (!await this.ensureNext()) {
                this.locked = false;
                return;
            }

            void this.saveExplanation(this.current);
            if (recordSkip && !await this.recordSkip(this.current.card)) {
                this.locked = false;
                return;
            }

            const oldPrevious = this.previous;
            const oldCurrent = this.current;
            const oldNext = this.next;
            const oldBuffered = this.buffered;

            this.setPosition(oldCurrent, "previous");
            this.setPosition(oldNext, "current");
            if (oldBuffered?.card) this.setPosition(oldBuffered, "next");
            await this.afterAnimation();

            this.previous = oldCurrent;
            this.current = oldNext;
            if (oldBuffered?.card) {
                this.next = oldBuffered;
                this.buffered = oldPrevious;
                if (oldPrevious) {
                    oldPrevious.card = null;
                    oldPrevious.element.removeAttribute("data-card-id");
                    oldPrevious.element.replaceChildren();
                    this.setPosition(oldPrevious, "buffered", true);
                }
            } else {
                this.buffered = null;
                this.next = oldPrevious;
                if (this.next) {
                    this.next.card = null;
                    if (!this.queue.length) await this.refill();
                    if (this.queue.length) this.renderCard(this.next, this.queue.shift());
                    this.setPosition(this.next, "next", true);
                }
            }

            this.answerPending = false;
            this.locked = false;
            this.status.classList.add("is-hidden");
            this.updateCurrentMetadata();
            void this.refill();
        }

        async movePrevious() {
            if (this.locked || this.answerPending || !this.previous?.card) return;
            this.locked = true;
            void this.saveExplanation(this.current);
            const oldPrevious = this.previous;
            const oldCurrent = this.current;
            const oldNext = this.next;

            this.setPosition(oldPrevious, "current");
            this.setPosition(oldCurrent, "next");
            if (oldNext) this.setPosition(oldNext, "buffered");
            await this.afterAnimation();

            this.current = oldPrevious;
            this.next = oldCurrent;
            this.previous = null;
            this.buffered = oldNext;
            this.locked = false;
            this.updateCurrentMetadata();
        }

        afterAnimation() {
            return new Promise((resolve) => setTimeout(resolve, ANIMATION_MS));
        }

        async recordSkip(card, confirmed = false) {
            try {
                const response = await fetch(this.routes.skipAttempt, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        card_id: card.id,
                        card_type: card.type,
                        confirmed,
                    }),
                });
                const payload = await response.json();
                if (response.status === 403 && payload.login_url) {
                    window.location.href = payload.login_url;
                    return false;
                }
                if (response.status === 409 && payload.status === "confirmation_required") {
                    if (!window.confirm("Если перелистнуть, серия обнулится. Перелистываем?")) {
                        return false;
                    }
                    return this.recordSkip(card, true);
                }
                if (!response.ok) throw new Error(payload.message);
                this.updateStrike({n: payload.strike, levels: this.strikeLevels});
                this.updateAnonymousRemaining(payload.anonymous_remaining);
                return true;
            } catch (error) {
                this.showStatus(error.message || "Не удалось сохранить пропуск");
                return false;
            }
        }

        async answer(button) {
            if (this.locked || this.answerPending || !this.current.card) return;
            this.answerPending = true;
            const buttons = this.current.element.querySelectorAll(".answers button");
            buttons.forEach((item) => { item.disabled = true; });
            try {
                const response = await fetch(this.routes.createAttempt, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        card_id: this.current.card.id,
                        card_type: this.current.card.type,
                        answer: button.dataset.answer,
                    }),
                });
                const payload = await response.json();
                if (response.status === 403 && payload.login_url) {
                    window.location.href = payload.login_url;
                    return;
                }
                if (!response.ok) throw new Error(payload.message);
                this.updateAnonymousRemaining(payload.anonymous_remaining);
                const nextLevel = this.updateStrike(payload.strike);
                this.revealAnswer(payload.full_word);
                this.flashAnswer(payload.correct, nextLevel);
                setTimeout(() => void this.moveNext({recordSkip: false}), payload.correct ? 700 : 1500);
            } catch (error) {
                this.answerPending = false;
                buttons.forEach((item) => { item.disabled = false; });
                this.showStatus(error.message || "Не удалось отправить ответ");
            }
        }

        revealAnswer(fullWord) {
            const word = this.current.element.querySelector(".word");
            word.classList.add("shrink");
            setTimeout(() => {
                word.textContent = fullWord;
            }, 200);
        }

        flashAnswer(correct, nextLevel) {
            const rect = this.current.element.querySelector(".word").getBoundingClientRect();
            const feedRect = this.feed.getBoundingClientRect();
            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;
            const start = performance.now();
            const duration = correct ? 720 : 480;
            const color = nextLevel ? [255, 210, 30] : correct ? [55, 225, 95] : [255, 65, 35];
            const maxRadius = Math.max(
                Math.hypot(centerX - feedRect.left, centerY - feedRect.top),
                Math.hypot(centerX - feedRect.right, centerY - feedRect.top),
                Math.hypot(centerX - feedRect.left, centerY - feedRect.bottom),
                Math.hypot(centerX - feedRect.right, centerY - feedRect.bottom),
            );
            const draw = (now) => {
                const progress = Math.min(1, (now - start) / duration);
                const fade = 1 - progress;
                const eased = 1 - Math.pow(1 - progress, 3);
                this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                this.ctx.save();
                this.ctx.scale(this.canvasScale, this.canvasScale);
                this.ctx.beginPath();
                this.ctx.rect(feedRect.left, feedRect.top, feedRect.width, feedRect.height);
                this.ctx.clip();

                if (correct) {
                    const radius = 16 + maxRadius * eased;
                    const glow = this.ctx.createRadialGradient(
                        centerX, centerY, Math.max(0, radius * .12),
                        centerX, centerY, radius,
                    );
                    glow.addColorStop(0, `rgba(${color.join(",")},${.025 * fade})`);
                    glow.addColorStop(.7, `rgba(${color.join(",")},${.07 * fade})`);
                    glow.addColorStop(.88, `rgba(${color.join(",")},${.16 * fade})`);
                    glow.addColorStop(1, `rgba(${color.join(",")},0)`);
                    this.ctx.fillStyle = glow;
                    this.ctx.beginPath();
                    this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
                    this.ctx.fill();

                    this.ctx.strokeStyle = `rgba(${color.join(",")},${.38 * fade})`;
                    this.ctx.lineWidth = 7 + 9 * fade;
                    this.ctx.shadowColor = `rgba(${color.join(",")},${.55 * fade})`;
                    this.ctx.shadowBlur = 24;
                    this.ctx.beginPath();
                    this.ctx.arc(centerX, centerY, radius * .9, 0, Math.PI * 2);
                    this.ctx.stroke();
                } else {
                    const intensity = Math.sin(Math.PI * progress) * .16;
                    const vignette = this.ctx.createRadialGradient(
                        centerX, centerY, 0,
                        centerX, centerY, maxRadius,
                    );
                    vignette.addColorStop(0, `rgba(${color.join(",")},${intensity * .15})`);
                    vignette.addColorStop(1, `rgba(${color.join(",")},${intensity})`);
                    this.ctx.fillStyle = vignette;
                    this.ctx.fillRect(feedRect.left, feedRect.top, feedRect.width, feedRect.height);
                }
                this.ctx.restore();
                if (progress < 1) requestAnimationFrame(draw);
                else this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            };
            requestAnimationFrame(draw);
        }

        updateStrike(strike) {
            if (!strike || strike.n === null || strike.n === undefined) return false;
            const value = document.getElementById("strike-value");
            if (value) value.textContent = strike.n;
            if (!this.isAnonymous) {
                const showHeaderInfo = strike.n > 5;
                clearTimeout(this.headerInfoTimer);
                if (showHeaderInfo) {
                    this.headerInfo.dataset.state = "neutral";
                    this.headerInfo.hidden = false;
                    requestAnimationFrame(() => {
                        this.headerInfo.classList.add("is-visible");
                    });
                } else {
                    this.headerInfo.classList.remove("is-visible");
                    this.headerInfoTimer = setTimeout(() => {
                        if (!this.headerInfo.classList.contains("is-visible")) {
                            this.headerInfo.hidden = true;
                        }
                    }, 240);
                }
                this.header.classList.toggle("has-info", showHeaderInfo);
            }
            const level = this.levelForStrike(
                strike.n,
                strike.levels || this.strikeLevels,
            );
            this.headerInfo.dataset.strikeLevel = String(Math.min(level, 4));
            return false;
        }

        levelForStrike(strike, levels = this.strikeLevels) {
            const level = levels.findIndex((threshold) => strike < threshold);
            return level < 0 ? levels.length : level;
        }

        backgroundFor(theme) {
            const choices = this.backgroundPools[theme] || [];
            if (!choices.length) return null;
            let queue = this.backgroundQueues.get(theme) || [];
            if (!queue.length) {
                queue = [...choices];
                for (let index = queue.length - 1; index > 0; index -= 1) {
                    const target = Math.floor(Math.random() * (index + 1));
                    [queue[index], queue[target]] = [queue[target], queue[index]];
                }
                const previous = this.lastBackgrounds.get(theme);
                if (queue.length > 1 && queue[0] === previous) {
                    [queue[0], queue[1]] = [queue[1], queue[0]];
                }
                this.backgroundQueues.set(theme, queue);
            }
            const url = queue.shift();
            this.lastBackgrounds.set(theme, url);
            return url;
        }

        assignBackground(element, theme, url = this.backgroundFor(theme)) {
            if (!element || !url) return;
            element.style.setProperty("--card-back-img", `url("${url}")`);
            element.dataset.backgroundTheme = theme;
        }

        updateAnonymousRemaining(remaining) {
            if (remaining === null || remaining === undefined) return;
            if (!this.isAnonymous || this.anonymousStarted) return;
            this.anonymousStarted = true;
            clearTimeout(this.headerInfoTimer);
            this.headerInfo.dataset.state = "accent";
            this.headerInfo.hidden = false;
            requestAnimationFrame(() => {
                this.headerInfo.classList.add("is-visible");
            });
            this.header.classList.add("has-info", "has-anonymous-info");
        }

        updateCurrentMetadata() {
            if (!this.current?.card) return;
            const card = this.current.card;
            this.info.textContent = card.info.join(" · ");
            document.getElementById("current-word").textContent = card.prompt;
            const task = card.task || {};
            document.getElementById("card-task").textContent = task.number
                ? `${task.number}. ${task.title || "Задание ЕГЭ"}`
                : "Не указано";
            const stats = card.stats || {};
            document.getElementById("word-correct").textContent = stats.correct || 0;
            document.getElementById("word-mistakes").textContent = stats.mistakes || 0;
            document.getElementById("word-skips").textContent = stats.skips || 0;
            document.getElementById("word-percent").textContent = `${stats.correct_percent || 0}%`;
            const report = document.getElementById("report-button");
            report.disabled = card.type !== "spelling";
            report.lastChild.textContent = report.disabled
                ? " Недоступно для этого задания"
                : " Сообщить об ошибке";
        }

        endpointFor(template, id) {
            return template.replace("/0/", `/${id}/`);
        }

        async saveExplanation(slot) {
            if (!this.admin || !slot?.card || slot.card.type !== "spelling") return;
            const input = slot.element.querySelector(".explanation");
            if (!input || input.value === input.dataset.initialValue) return;
            const value = input.value;
            input.dataset.initialValue = value;
            try {
                await fetch(this.endpointFor(this.routes.updateExplanation, slot.card.id), {
                    method: "PATCH",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({explanation: value}),
                });
            } catch {
                input.dataset.initialValue = "\u0000";
            }
        }

        async deleteAnswer(button) {
            const answer = button.dataset.answer;
            const response = await fetch(
                this.endpointFor(this.routes.deleteAnswer, this.current.card.id),
                {
                    method: "DELETE",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({answer}),
                },
            );
            if (response.ok) button.remove();
        }

        openPanel(name, trigger = null) {
            if (name === "word" && !this.current?.card) return;
            if (this.activePanel?.dataset.panel === name) {
                this.closePanel();
                return;
            }
            this.closePanel(false);
            clearTimeout(this.panelCloseTimer);
            this.closingPanel?.classList.remove("is-closing");
            this.closingTrigger?.classList.remove("is-panel-trigger-active");
            this.closingPanel = null;
            this.closingTrigger = null;
            this.panelOverlay.classList.remove("is-closing");
            this.header.classList.remove("is-closing-profile");
            const panel = this.panels.find((item) => item.dataset.panel === name);
            if (!panel) return;
            this.activePanel = panel;
            this.panelTrigger = trigger;
            this.header.classList.add("has-open-panel");
            this.header.classList.toggle("has-profile-panel", name === "profile");
            trigger?.classList.add("is-panel-trigger-active");
            panel.classList.add("is-open");
            panel.setAttribute("aria-hidden", "false");
            clearTimeout(this.panelCloseTimer);
            this.panelOverlay.hidden = false;
            requestAnimationFrame(() => this.panelOverlay.classList.add("is-open"));
            document.body.classList.add("has-open-panel");
            panel.querySelector("button, a, input")?.focus({preventScroll: true});
        }

        closePanel(restoreFocus = true) {
            if (!this.activePanel) return;
            const panel = this.activePanel;
            const trigger = this.panelTrigger;
            const closesProfile = panel.dataset.panel === "profile";
            panel.classList.remove("is-open");
            panel.classList.add("is-closing");
            panel.setAttribute("aria-hidden", "true");
            this.panelOverlay.classList.remove("is-open");
            this.panelOverlay.classList.add("is-closing");
            document.body.classList.remove("has-open-panel");
            this.header.classList.remove("has-open-panel", "has-profile-panel");
            if (closesProfile) {
                this.header.classList.add("is-closing-profile");
            }
            trigger?.classList.remove("is-panel-trigger-active");
            this.activePanel = null;
            this.panelTrigger = null;
            this.closingPanel = panel;
            this.closingTrigger = trigger;
            clearTimeout(this.panelCloseTimer);
            this.panelCloseTimer = setTimeout(() => {
                if (this.activePanel || this.closingPanel !== panel) return;
                panel.classList.remove("is-closing");
                this.panelOverlay.classList.remove("is-closing");
                this.panelOverlay.hidden = true;
                this.header.classList.remove("is-closing-profile");
                this.closingPanel = null;
                this.closingTrigger = null;
            }, 280);
            if (restoreFocus) trigger?.focus();
        }

        showStatus(message) {
            this.status.textContent = message;
            this.status.classList.remove("is-hidden");
            if (this.current?.card) setTimeout(() => this.status.classList.add("is-hidden"), 2500);
        }

        resizeCanvas() {
            this.canvasScale = Math.min(window.devicePixelRatio || 1, 2);
            this.canvas.width = Math.round(window.innerWidth * this.canvasScale);
            this.canvas.height = Math.round(window.innerHeight * this.canvasScale);
        }

        bindEvents() {
            this.feed.addEventListener("click", (event) => {
                const answer = event.target.closest("[data-answer]");
                if (answer && !this.suppressAnswerClick) void this.answer(answer);
                this.suppressAnswerClick = false;
            });

            this.feed.addEventListener("pointerdown", (event) => {
                const answer = event.target.closest("[data-answer]");
                if (answer && this.admin && this.current.card?.type === "spelling") {
                    this.answerLongPressTimer = setTimeout(() => {
                        this.suppressAnswerClick = true;
                        void this.deleteAnswer(answer);
                    }, 500);
                    return;
                }
                if (event.target.closest("button, a, textarea")) return;
                this.pointer = {id: event.pointerId, x: event.clientX, y: event.clientY};
                this.longPressOpened = false;
                this.longPressTimer = setTimeout(() => {
                    this.longPressOpened = true;
                    this.openPanel(
                        "word",
                        document.querySelector('[data-open-panel="word"]'),
                    );
                }, 500);
            });

            this.feed.addEventListener("pointermove", (event) => {
                if (!this.pointer || event.pointerId !== this.pointer.id) return;
                if (Math.abs(event.clientY - this.pointer.y) > 10) clearTimeout(this.longPressTimer);
            });

            const finishPointer = (event) => {
                clearTimeout(this.answerLongPressTimer);
                if (!this.pointer || event.pointerId !== this.pointer.id) return;
                clearTimeout(this.longPressTimer);
                const deltaY = event.clientY - this.pointer.y;
                this.pointer = null;
                if (this.longPressOpened) return;
                if (deltaY < -50) void this.moveNext();
                else if (deltaY > 50) void this.movePrevious();
            };
            this.feed.addEventListener("pointerup", finishPointer);
            this.feed.addEventListener("pointercancel", finishPointer);

            let wheelReady = true;
            document.addEventListener("wheel", (event) => {
                if (!wheelReady || this.activePanel) return;
                wheelReady = false;
                if (event.deltaY > 0) void this.moveNext();
                else void this.movePrevious();
                setTimeout(() => { wheelReady = true; }, ANIMATION_MS);
            }, {passive: true});

            document.addEventListener("keydown", (event) => {
                if (event.key === "Escape" && this.activePanel) {
                    this.closePanel();
                    return;
                }
                if (event.target.matches("textarea, input") || this.activePanel) return;
                if (["ArrowDown", "s", " "].includes(event.key)) {
                    event.preventDefault();
                    void this.moveNext();
                } else if (["ArrowUp", "w"].includes(event.key)) {
                    event.preventDefault();
                    void this.movePrevious();
                }
            });

            document.querySelectorAll("[data-open-panel]").forEach((trigger) => {
                trigger.addEventListener("click", () => {
                    this.openPanel(trigger.dataset.openPanel, trigger);
                });
            });
            document.querySelectorAll("[data-close-panel]").forEach((trigger) => {
                trigger.addEventListener("click", () => this.closePanel());
            });
            const strikeToggle = document.querySelector("[data-strike-toggle]");
            strikeToggle?.addEventListener("click", async () => {
                const enabled = strikeToggle.getAttribute("aria-pressed") !== "true";
                strikeToggle.disabled = true;
                try {
                    const response = await fetch(this.routes.updateSettings, {
                        method: "PATCH",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({strike: enabled}),
                    });
                    if (!response.ok) throw new Error();
                    strikeToggle.setAttribute("aria-pressed", String(enabled));
                    if (!enabled) {
                        this.headerInfo.classList.remove("is-visible");
                        this.headerInfo.hidden = true;
                        this.header.classList.remove("has-info");
                    }
                } catch {
                    this.showStatus("Не удалось изменить настройку");
                } finally {
                    strikeToggle.disabled = false;
                }
            });
            this.panelOverlay.addEventListener("click", () => this.closePanel());
            document.getElementById("report-button").addEventListener("click", async (event) => {
                const response = await fetch(
                    this.endpointFor(this.routes.reportWord, this.current.card.id),
                    {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"},
                );
                if (response.ok) {
                    event.currentTarget.lastChild.textContent = " Запрос отправлен";
                    event.currentTarget.disabled = true;
                }
            });
            document.getElementById("search-button").addEventListener("click", () => {
                const query = encodeURIComponent(this.current.card.prompt);
                window.open(`https://yandex.ru/search/?text=${query}`, "_blank", "noopener");
            });
            window.addEventListener("resize", () => this.resizeCanvas(), {passive: true});
        }

    }

    document.addEventListener("DOMContentLoaded", () => {
        const feed = new FeedController(window.feedBootstrap, window.routeConfig);
        window.feedController = feed;
        void feed.start();
    });
})();
