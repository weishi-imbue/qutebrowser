/* eslint-disable no-extend-native,no-implicit-globals */

"use strict";

// Based on: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at
/**
 * Array.prototype.at() polyfill
 * https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/at
 * Provides support for negative indexing and boundary checking
 */
if (!Array.prototype.at) {
    Array.prototype.at = function(index) {
        // Convert the index to an integer
        index = Math.trunc(index) || 0;

        // Handle negative indices by calculating from the end
        if (index < 0) {
            index += this.length;
        }

        // Return undefined if index is out of bounds
        if (index < 0 || index >= this.length) {
            return undefined;
        }

        // Return the element at the calculated index
        return this[index];
    };
}