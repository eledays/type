(function exposeAnalyticsSearch(root, factory) {
    "use strict";
    const helpers = factory();
    if (typeof module === "object" && module.exports) {
        module.exports = helpers;
    } else {
        root.analyticsSearch = helpers;
    }
}(typeof window === "undefined" ? {} : window, () => {
    "use strict";

    function meaningfulLength(value) {
        const characters = value.normalize("NFKC").match(/[\p{L}\p{N}]/gu);
        return characters ? characters.length : 0;
    }

    function isReady(value) {
        const trimmed = value.trim();
        return !trimmed || meaningfulLength(trimmed) >= 2;
    }

    return { meaningfulLength, isReady };
}));
