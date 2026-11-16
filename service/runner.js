/* ES5 / Node 0.12 compatible. No shell, no network and one short-lived worker. */
'use strict';
var spawn = require('child_process').spawn;
var path = require('path');
var LIMIT = 2 * 1024 * 1024;
var active = false;
var ALLOWED = {health: true, analyzeStreams: true, parseSubtitles: true, catalog: true};
module.exports = function run(payload, respond, binary) {
  if (!payload || !Object.prototype.hasOwnProperty.call(ALLOWED, payload.cmd)) { respond({returnValue: false, errorText: 'Unknown command'}); return; }
  if (active) { respond({returnValue: false, errorText: 'Native core busy'}); return; }
  var input;
  try { input = JSON.stringify(payload); } catch (e) { respond({returnValue: false, errorText: 'Invalid input'}); return; }
  if (Buffer.byteLength(input, 'utf8') > LIMIT) { respond({returnValue: false, errorText: 'Request too large'}); return; }
  active = true;
  var done = false, output = '', bytes = 0, child, timer;
  function finish(response) {
    if (done) { return; }
    done = true;
    clearTimeout(timer);
    // Keep the concurrency guard until the worker has actually exited.
    respond(response);
  }
  try {
    child = spawn(binary || path.join(__dirname, 'streamlite-core'), [], {stdio: ['pipe', 'pipe', 'ignore']});
  } catch (e2) {
    active = false;
    finish({returnValue: false, errorText: 'Native core could not start'});
    return;
  }
  timer = setTimeout(function () {
    child.kill('SIGKILL');
    finish({returnValue: false, errorText: 'Native core timeout'});
  }, 3000);
  child.on('error', function () {
    active = false;
    finish({returnValue: false, errorText: 'Native core unavailable'});
  });
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', function (chunk) {
    bytes += Buffer.byteLength(chunk, 'utf8');
    if (bytes > LIMIT) {
      child.kill('SIGKILL');
      finish({returnValue: false, errorText: 'Native response too large'});
    } else { output += chunk; }
  });
  child.stdin.on('error', function () {});
  child.on('close', function (code) {
    active = false;
    if (done) { return; }
    if (code !== 0) { finish({returnValue: false, errorText: 'Native core failed'}); return; }
    try { finish(JSON.parse(output)); }
    catch (e) { finish({returnValue: false, errorText: 'Invalid native response'}); }
  });
  child.stdin.end(input);
};
