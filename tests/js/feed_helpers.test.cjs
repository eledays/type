const test = require("node:test");
const assert = require("node:assert/strict");

const {RequestRegistry, uniqueIntegerIds} = require(
    "../../app/static/js/feed-helpers.js",
);

test("request id survives ambiguous retries until explicitly released", () => {
    let sequence = 0;
    const requests = new RequestRegistry(() => `request-${++sequence}`);

    assert.equal(requests.acquire("answer:42:о"), "request-1");
    assert.equal(requests.acquire("answer:42:о"), "request-1");
    assert.equal(sequence, 1);

    requests.release("answer:42:о");
    assert.equal(requests.acquire("answer:42:о"), "request-2");
});

test("request ids remain independent for answer and skip operations", () => {
    let sequence = 0;
    const requests = new RequestRegistry(() => `request-${++sequence}`);

    assert.equal(requests.acquire("answer:7:а"), "request-1");
    assert.equal(requests.acquire("skip:7"), "request-2");
    assert.equal(requests.acquire("answer:7:а"), "request-1");
});

test("active ids are integer-only and preserve first-seen order", () => {
    assert.deepEqual(uniqueIntegerIds([3, null, 2, 3, "4", 2]), [3, 2]);
});
