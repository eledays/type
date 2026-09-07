const test = require("node:test");
const assert = require("node:assert/strict");

const search = require("../../app/static/js/analytics-search.js");

test("search requires two meaningful Unicode characters", () => {
    assert.equal(search.isReady(""), true);
    assert.equal(search.isReady("а"), false);
    assert.equal(search.isReady("___!?"), false);
    assert.equal(search.isReady("эк"), true);
    assert.equal(search.isReady("42"), true);
});

test("placeholder punctuation is not counted as searchable text", () => {
    assert.equal(search.meaningfulLength(" экз_ме "), 5);
    assert.equal(search.meaningfulLength("___"), 0);
});
