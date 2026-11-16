/* ES5 bridge. The app still works if the native service cannot run on a TV. */
(function () {
  'use strict';
  var pending = [];
  var status = 'fallback ES5';
  window.StreamLiteNative = {
    status: function () { return status; },
    run: function (cmd, payload, cb) {
      if (!window.PalmServiceBridge) { cb(new Error('Native bridge unavailable')); return; }
      var bridge, timer, done = false;
      function finish(err, value) {
        if (done) { return; }
        done = true;
        if (err && err.message !== 'Native core busy') { status = 'fallback ES5'; }
        clearTimeout(timer);
        var index = pending.indexOf(bridge);
        if (index >= 0) { pending.splice(index, 1); }
        if (bridge) {
          bridge.onservicecallback = null;
          if (bridge.cancel) { try { bridge.cancel(); } catch (ignore) {} }
        }
        cb(err, value);
      }
      try {
        bridge = new window.PalmServiceBridge();
        pending.push(bridge);
        bridge.onservicecallback = function (raw) {
          var response;
          try { response = JSON.parse(raw); } catch (e) { finish(new Error('Invalid native response')); return; }
          if (!response.returnValue) { finish(new Error(response.errorText || 'Native core unavailable')); return; }
          if (status === 'fallback ES5') { status = 'Rust nativo ARM'; }
          if (cmd === 'health' && response.result) { status = 'Rust nativo ARM' + (response.result.armAsm ? ' + Assembly ARM' : ''); }
          finish(null, response.result);
        };
        timer = setTimeout(function () { finish(new Error('Native core timeout')); }, 4000);
        payload.cmd = cmd;
        bridge.call('luna://org.streamlite.webos.service/run', JSON.stringify(payload));
      } catch (e2) { finish(e2); }
    }
  };
})();
