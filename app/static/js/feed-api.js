(function exposeFeedApi(root, factory) {
    "use strict";
    if (typeof module === "object" && module.exports) {
        module.exports = factory(require("./feed-helpers.js"));
    } else {
        root.feedApi = factory(root.feedHelpers);
    }
}(typeof window === "undefined" ? {} : window, (helpers) => {
    "use strict";

    class FeedApi {
        constructor(routes, createRequestId, fetchImplementation = fetch) {
            this.routes = routes;
            this.fetch = fetchImplementation;
            this.requestIds = new helpers.RequestRegistry(createRequestId);
        }

        requestIdFor(key) {
            return this.requestIds.acquire(key);
        }

        releaseRequestId(key) {
            this.requestIds.release(key);
        }

        async json(url, options) {
            const response = await this.fetch(url, options);
            return {response, payload: await response.json()};
        }

        skip(card, confirmed, requestId) {
            return this.json(this.routes.skipAttempt, {
                method: "POST",
                headers: this.jsonHeaders(),
                body: JSON.stringify({
                    card_id: card.id,
                    card_type: card.type,
                    confirmed,
                    request_id: requestId,
                }),
            });
        }

        answer(card, answer, requestId) {
            return this.json(this.routes.createAttempt, {
                method: "POST",
                headers: this.jsonHeaders(),
                body: JSON.stringify({
                    card_id: card.id,
                    card_type: card.type,
                    answer,
                    request_id: requestId,
                }),
            });
        }

        createReport(message, practiceItemId) {
            return this.json(this.routes.createReport, {
                method: "POST",
                headers: this.jsonHeaders(),
                body: JSON.stringify({
                    message,
                    practice_item_id: practiceItemId,
                }),
            });
        }

        updateSettings(settings) {
            return this.fetch(this.routes.updateSettings, {
                method: "PATCH",
                headers: this.jsonHeaders(),
                body: JSON.stringify(settings),
            });
        }

        jsonHeaders() {
            return {
                "Content-Type": "application/json",
                "X-CSRFToken": this.routes.csrfToken,
            };
        }
    }

    return {FeedApi};
}));
