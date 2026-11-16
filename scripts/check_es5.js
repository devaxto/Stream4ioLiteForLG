// Parse every shipped JavaScript file as ES5 for Chromium 38/53.
// Usage: npm ci && npm run check
var fs = require('fs');
var path = require('path');
var acorn = require('acorn');
var app = path.join(__dirname, '..', 'app');
['app.js', 'native.js', 'config.example.js'].forEach(function (file) {
  try {
    acorn.parse(fs.readFileSync(path.join(app, file), 'utf8'), { ecmaVersion: 5 });
    console.log('OK: ' + file + ' is valid ES5');
  } catch (e) {
    console.error(file + ' is NOT ES5:', e.message);
    process.exit(1);
  }
});
['service.js', 'runner.js'].forEach(function (file) {
  acorn.parse(fs.readFileSync(path.join(app, '..', 'service', file), 'utf8'), { ecmaVersion: 5 });
  console.log('OK: service/' + file + ' is valid ES5');
});
