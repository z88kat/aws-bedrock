# aws-bedrock — buggy demo server

A deliberately buggy Node.js / Express server that emits realistic errors via
[Winston](https://github.com/winstonjs/winston). It exists as a test subject for
an AI debugging agent that will capture these errors, inspect the source in this
repo, and open pull requests suggesting fixes.

The server **fails roughly every 2 minutes** (with jitter) by running a randomly
chosen helper function that contains a genuine bug. Every error is caught and
written to a structured JSON log file; the process stays alive and keeps
producing new errors.

## Run

```bash
npm install
npm start        # or: npm run dev  (auto-restart on file changes)
```

Server listens on `http://localhost:3000` (override with `PORT`).

## Endpoints

| Method     | Path               | Description                                  |
| ---------- | ------------------ | -------------------------------------------- |
| GET        | `/health`          | Always-OK health check.                      |
| GET        | `/tasks`           | List the available buggy task names.         |
| GET/POST   | `/trigger/:name`   | Run one buggy task on demand by name.        |
| ANY        | `/boom`            | Trigger a random failure immediately.        |

Example:

```bash
curl localhost:3000/trigger/parseConfig
curl localhost:3000/boom
```

## Logs

Written to the `logs/` directory (gitignored):

- `logs/error.log` — errors only, structured JSON (what the agent reads).
- `logs/combined.log` — all log lines, structured JSON.
- Console — colourised, human-readable.

Each error entry includes `message`, `stack`, `errorType`, `task`, `source`,
`timestamp`, and `trigger`, so an error can be traced straight back to the
offending function in [`src/buggyTasks.js`](src/buggyTasks.js).

## The bugs

All live in [`src/buggyTasks.js`](src/buggyTasks.js). Each is a real, diagnosable
mistake with the root cause documented in a comment above it:

| Task              | Bug                              | Error type      |
| ----------------- | -------------------------------- | --------------- |
| `formatUserName`  | reads wrong property name        | `TypeError`     |
| `parseConfig`     | parses malformed JSON            | `SyntaxError`   |
| `getShippingCity` | null nested object deref         | `TypeError`     |
| `countItems`      | typo `.lenght()`                 | `TypeError`     |
| `averagePrice`    | off-by-one loop → `NaN`          | `RangeError`    |
| `buildSlug`       | calls an undefined function      | `ReferenceError`|
| `deepProcess`     | wrong recursion base case        | `Error`         |

## Project layout

```
src/
  server.js          Express app, routes, process-level error nets
  logger.js          Winston setup (JSON files + pretty console)
  buggyTasks.js      the buggy helper functions + task registry
  errorScheduler.js  randomized ~2-minute failure timer
```
