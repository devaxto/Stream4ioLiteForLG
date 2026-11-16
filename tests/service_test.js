'use strict';
var assert = require('assert');
var path = require('path');
var run = require('../service/runner');
var binary = process.env.STREAMLITE_CORE || path.join(__dirname, '../native/target/release/streamlite-core');
function call(payload, executable) {
  return new Promise(function (resolve) { run(payload, resolve, executable || binary); });
}
(async function () {
  var health = await call({cmd: 'health'});
  assert.strictEqual(health.returnValue, true);
  assert.strictEqual(health.result.engine, 'rust-native');
  var catalog = await call({cmd:'catalog', metas:[{id:'tt1'}, {id:'tt1'}, {id:'tt2'}]});
  assert.strictEqual(catalog.result.length, 2);
  var analyzed = await call({cmd:'analyzeStreams', streams:[{url:'https://x/video',title:'FILM.1080p.ITA.x264.AAC.mp4'}]});
  assert.strictEqual(analyzed.result[0].info.italian, true);
  var rejected = await call({cmd:'toString'});
  assert.strictEqual(rejected.returnValue, false);
  var oversized = await call({cmd:'parseSubtitles',text:'x'.repeat(2*1024*1024)});
  assert.strictEqual(oversized.returnValue, false);
  var unavailable = await call({cmd:'health'}, '/does-not-exist/streamlite-core');
  assert.strictEqual(unavailable.returnValue, false);
  // Wait for the failed spawn's close event before the next request.
  await new Promise(function(resolve){setImmediate(resolve);});
  var first = call({cmd:'health'});
  var busy = await call({cmd:'health'});
  assert.strictEqual(busy.returnValue, false);
  assert.strictEqual(busy.errorText, 'Native core busy');
  assert.strictEqual((await first).returnValue, true);
  console.log('PASS Luna worker: Rust round trips, bounds, allowlist, spawn failure, concurrency');
})().catch(function(error){console.error(error);process.exitCode=1;});
