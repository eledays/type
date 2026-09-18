(function exposeFeedHelpers(root, factory) {
    "use strict";
    const helpers = factory();
    if (typeof module === "object" && module.exports) {
        module.exports = helpers;
    } else {
        root.feedHelpers = helpers;
    }
}(typeof window === "undefined" ? {} : window, () => {
    "use strict";

    class RequestRegistry {
        constructor(createId) {
            this.createId = createId;
            this.pending = new Map();
        }

        acquire(key) {
            if (!this.pending.has(key)) this.pending.set(key, this.createId());
            return this.pending.get(key);
        }

        release(key) {
            this.pending.delete(key);
        }
    }

    function uniqueIntegerIds(values) {
        return [...new Set(values.filter(Number.isInteger))];
    }

    return { RequestRegistry, uniqueIntegerIds };
}));
