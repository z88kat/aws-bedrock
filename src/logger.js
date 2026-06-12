'use strict';

const fs = require('fs');
const path = require('path');
const winston = require('winston');

// Ensure the logs directory exists before any transport tries to write to it.
const logDir = path.join(__dirname, '..', 'logs');
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}

// Structured JSON for the files (easy for the AI agent to parse: message,
// stack, level, timestamp and any extra metadata we attach to an error).
const fileFormat = winston.format.combine(
  winston.format.timestamp(),
  winston.format.errors({ stack: true }),
  winston.format.json()
);

// Human-friendly colourised output for the console.
const consoleFormat = winston.format.combine(
  winston.format.colorize(),
  winston.format.timestamp({ format: 'HH:mm:ss' }),
  winston.format.printf(({ timestamp, level, message, stack }) => {
    return `${timestamp} ${level}: ${stack || message}`;
  })
);

const logger = winston.createLogger({
  level: 'info',
  format: fileFormat,
  transports: [
    // Everything goes to combined.log...
    new winston.transports.File({
      filename: path.join(logDir, 'combined.log'),
    }),
    // ...and errors are additionally isolated in error.log for the agent.
    new winston.transports.File({
      filename: path.join(logDir, 'error.log'),
      level: 'error',
    }),
    new winston.transports.Console({ format: consoleFormat }),
  ],
});

module.exports = logger;
