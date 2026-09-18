"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {FeedApi} = require("../../app/static/js/feed-api.js");

function response(payload = {ok: true}) {
    return {ok: true, json: async () => payload};
}

test("attempt client sends stable ids, card type and CSRF token", async () => {
    const calls = [];
    let fetchReceiver = "not-called";
    async function fetchStub(...args) {
        fetchReceiver = this;
        calls.push(args);
        return response();
    }
    const api = new FeedApi(
        {
            createAttempt: "/attempts",
            csrfToken: "csrf-42",
        },
        () => "request-42",
        fetchStub,
    );
    const requestId = api.requestIdFor("answer:7:о");

    await api.answer({id: 7, type: "spelling"}, "о", requestId);

    const [url, options] = calls[0];
    assert.equal(fetchReceiver, undefined);
    assert.equal(url, "/attempts");
    assert.equal(options.headers["X-CSRFToken"], "csrf-42");
    assert.deepEqual(JSON.parse(options.body), {
        card_id: 7,
        card_type: "spelling",
        answer: "о",
        request_id: "request-42",
    });
});

test("report client preserves a null practice item context", async () => {
    let body;
    const api = new FeedApi(
        {createReport: "/reports", csrfToken: "csrf"},
        () => "unused",
        async (_url, options) => {
            body = JSON.parse(options.body);
            return response();
        },
    );

    await api.createReport("Общая ошибка", null);

    assert.deepEqual(body, {
        message: "Общая ошибка",
        practice_item_id: null,
    });
});
