'use strict';

const logger = require('./logger');
const { tasks } = require('./buggyTasks');

// Base interval (~2 minutes) with jitter so failures don't look robotic.
const BASE_INTERVAL_MS = 2 * 60 * 1000;
const JITTER_MS = 30 * 1000;

let timer = null;

function pickRandomTask() {
  const index = Math.floor(Math.random() * tasks.length);
  return tasks[index];
}

function nextDelay() {
  // BASE ± JITTER, never less than 10s.
  const offset = Math.floor(Math.random() * (2 * JITTER_MS)) - JITTER_MS;
  return Math.max(10 * 1000, BASE_INTERVAL_MS + offset);
}

// Run one buggy task, catch whatever it throws, and log it richly so the AI
// agent can map the error back to source.
function triggerOnce() {
  const task = pickRandomTask();
  try {
    task.run();
    logger.info(`Task "${task.name}" unexpectedly succeeded`);
  } catch (err) {
    logger.error(err.message, {
      task: task.name,
      errorType: err.constructor.name,
      stack: err.stack,
      source: 'src/buggyTasks.js',
      trigger: 'scheduler',
    });
  }
}

function scheduleNext() {
  const delay = nextDelay();
  logger.info(`Next failure scheduled in ${Math.round(delay / 1000)}s`);
  timer = setTimeout(() => {
    triggerOnce();
    scheduleNext();
  }, delay);
}

function start() {
  logger.info('Error scheduler started — generating failures every ~2 minutes');
  // Fire one shortly after boot so there's something in the log immediately.
  timer = setTimeout(() => {
    triggerOnce();
    scheduleNext();
  }, 5 * 1000);
}

function stop() {
  if (timer) {
    clearTimeout(timer);
    timer = null;
  }
}

module.exports = { start, stop, triggerOnce, pickRandomTask };
