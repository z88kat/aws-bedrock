'use strict';

const express = require('express');
const logger = require('./logger');
const scheduler = require('./errorScheduler');
const { tasks } = require('./buggyTasks');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

// Simple request logging.
app.use((req, _res, next) => {
  logger.info(`${req.method} ${req.url}`);
  next();
});

// Health check — the one endpoint that always works.
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', uptime: process.uptime() });
});

// List the available buggy tasks so you know what you can trigger.
app.get('/tasks', (_req, res) => {
  res.json({ tasks: tasks.map((t) => t.name) });
});

// Trigger a specific buggy task on demand by name, e.g. POST /trigger/parseConfig
// (or GET for convenience). Errors are caught, logged, and surfaced as a 500.
function handleTrigger(req, res) {
  const { name } = req.params;
  const task = tasks.find((t) => t.name === name);

  if (!task) {
    return res.status(404).json({ error: `Unknown task "${name}"` });
  }

  try {
    const result = task.run();
    return res.json({ task: task.name, result });
  } catch (err) {
    logger.error(err.message, {
      task: task.name,
      errorType: err.constructor.name,
      stack: err.stack,
      source: 'src/buggyTasks.js',
      trigger: 'http',
    });
    return res.status(500).json({
      task: task.name,
      error: err.message,
      errorType: err.constructor.name,
    });
  }
}

app.get('/trigger/:name', handleTrigger);
app.post('/trigger/:name', handleTrigger);

// Trigger a random failure immediately.
app.all('/boom', (_req, res) => {
  scheduler.triggerOnce();
  res.json({ status: 'triggered a random failure — check the logs' });
});

// Express error handler — last resort so a thrown error never kills the server.
app.use((err, _req, res, _next) => {
  logger.error(err.message, {
    stack: err.stack,
    errorType: err.constructor.name,
    trigger: 'express-error-handler',
  });
  res.status(500).json({ error: 'Internal Server Error' });
});

const server = app.listen(PORT, () => {
  logger.info(`Buggy demo server listening on http://localhost:${PORT}`);
  scheduler.start();
});

// Keep the process alive even if something escapes our try/catch nets, so the
// demo keeps producing errors instead of dying.
process.on('uncaughtException', (err) => {
  logger.error(err.message, {
    stack: err.stack,
    errorType: err.constructor.name,
    trigger: 'uncaughtException',
  });
});

process.on('unhandledRejection', (reason) => {
  logger.error('Unhandled promise rejection', {
    reason: reason instanceof Error ? reason.message : String(reason),
    stack: reason instanceof Error ? reason.stack : undefined,
    trigger: 'unhandledRejection',
  });
});

function shutdown(signal) {
  logger.info(`${signal} received — shutting down`);
  scheduler.stop();
  server.close(() => process.exit(0));
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

module.exports = app;
