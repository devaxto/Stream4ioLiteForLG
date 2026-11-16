'use strict';
var Service = require('webos-service');
var run = require('./runner');
var service = new Service('org.streamlite.webos.service');
service.register('run', function (message) {
  run(message.payload, function (response) { message.respond(response); });
});
