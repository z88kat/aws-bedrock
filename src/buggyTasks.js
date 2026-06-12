'use strict';

/*
 * A collection of helper functions that each contain a REAL, diagnosable bug.
 * These are intentionally written the way a tired developer might write them,
 * so that the downstream AI agent has genuine source code to locate and fix.
 *
 * Each function will throw when called. The bug, the root cause and a hint at
 * the fix are documented above each one so we can later check whether the agent
 * arrived at the right conclusion.
 */

// BUG: reads `.toUpperCase()` off a property that does not exist on the object,
// so `user.name` is `undefined` and the call throws a TypeError.
// ROOT CAUSE: the field is actually `fullName`, not `name`.
function formatUserName(user) {
  return user.name.toUpperCase();
}

// BUG: JSON.parse is given a malformed/truncated JSON string.
// ROOT CAUSE: the payload is missing a closing brace, so parsing throws a
// SyntaxError. A real fix would validate/guard the input before parsing.
function parseConfig() {
  const rawConfig = '{ "retries": 3, "timeout": 5000 ';
  return JSON.parse(rawConfig);
}

// BUG: accesses a property on a nested object that is null.
// ROOT CAUSE: `order.customer` is null for guest checkouts, so reading
// `.address.city` throws "Cannot read properties of null".
function getShippingCity(order) {
  return order.customer.address.city;
}

// BUG: calls a method that does not exist on the array.
// ROOT CAUSE: typo — `.lenght` instead of `.length`, then we call it as a
// function, producing a TypeError.
function countItems(items) {
  return items.lenght();
}

// BUG: divides and indexes past the end of an array.
// ROOT CAUSE: off-by-one — the loop condition uses `<=` so on the final
// iteration `prices[i]` is undefined and the arithmetic yields NaN, which we
// then assert against and throw.
function averagePrice(prices) {
  let total = 0;
  for (let i = 0; i <= prices.length; i++) {
    total += prices[i];
  }
  const average = total / prices.length;
  if (Number.isNaN(average)) {
    throw new RangeError('Computed average is NaN due to out-of-bounds access');
  }
  return average;
}

// BUG: calls an undefined function.
// ROOT CAUSE: the helper `slugify` was never imported/defined in this module.
function buildSlug(title) {
  return slugify(title); // eslint-disable-line no-undef
}

// BUG: infinite-ish recursion guard that throws a custom error.
// ROOT CAUSE: the base case is wrong (`n < 0` never hit for positive input),
// so we deliberately throw once depth is exceeded to simulate a stack issue.
function deepProcess(n, depth = 0) {
  if (depth > 50) {
    throw new Error('Maximum processing depth exceeded (runaway recursion)');
  }
  if (n < 0) {
    return n;
  }
  return deepProcess(n, depth + 1);
}

/*
 * Registry of tasks the scheduler and routes can pick from. Each entry is
 * self-contained: calling `run()` reproduces the bug with realistic inputs.
 */
const tasks = [
  {
    name: 'formatUserName',
    run: () => formatUserName({ fullName: 'Ada Lovelace', id: 1 }),
  },
  {
    name: 'parseConfig',
    run: () => parseConfig(),
  },
  {
    name: 'getShippingCity',
    run: () => getShippingCity({ id: 42, customer: null }),
  },
  {
    name: 'countItems',
    run: () => countItems([1, 2, 3]),
  },
  {
    name: 'averagePrice',
    run: () => averagePrice([9.99, 19.99, 4.5]),
  },
  {
    name: 'buildSlug',
    run: () => buildSlug('Hello World'),
  },
  {
    name: 'deepProcess',
    run: () => deepProcess(10),
  },
];

module.exports = {
  tasks,
  formatUserName,
  parseConfig,
  getShippingCity,
  countItems,
  averagePrice,
  buildSlug,
  deepProcess,
};
