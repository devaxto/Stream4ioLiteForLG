"""Offline UI regression tests. Native media is simulated, not hardware-validated.
Run: pip install -r tests/requirements.txt && playwright install chromium && npm test
Uses installed Chromium if available; all external requests are intercepted.
"""
import asyncio
import base64
import json
import os
import re
import shutil
import functools
import threading
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = Path(os.environ.get('STREAMLITE_APP', str(ROOT / 'app')))
OUT = ROOT / 'tests/out'
POSTER = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkqP9fDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
ADDONS = [
    {'transportUrl': 'https://cinemeta.example/manifest.json', 'manifest': {
        'id': 'com.linvo.cinemeta', 'name': 'Cinemeta', 'resources': ['catalog', 'meta'],
        'types': ['movie', 'series'], 'idPrefixes': ['tt'],
        'catalogs': [{'id': 'top', 'type': t, 'name': n, 'extra': [{'name': 'skip'}, {'name': 'search'}]}
                     for t, n in [('movie', 'Film'), ('series', 'Serie')]]}},
    {'transportUrl': 'https://streams.example/manifest.json', 'manifest': {
        'id': 'test.streams', 'name': 'Sorgenti test', 'resources': ['stream', 'subtitles'],
        'types': ['movie', 'series'], 'idPrefixes': ['tt']}}
]
STREAMS = [
    {'name': 'English', 'title': 'Film.1080p.x264.AAC.mp4 2 GB', 'url': 'https://video.example/en.mp4'},
    {'name': 'Italiano', 'title': 'Film.720p.ITA.x264.AAC.mp4 1 GB', 'url': 'https://video.example/it.mp4'},
    {'name': 'Pesante', 'title': 'Film.2160p.HDR.x265.DTS.mkv 25 GB', 'url': 'https://video.example/4k.mkv'},
    {'name': 'Torrent', 'title': 'Film.1080p.x264', 'infoHash': 'abc'}
]
MEDIA_STUB = """
window.testTimers = {};
window.testSeeks = [];
var nativeSetInterval = window.setInterval, nativeClearInterval = window.clearInterval;
window.setInterval = function(fn, ms) {
  var id = nativeSetInterval(fn, ms); window.testTimers[id] = ms; return id;
};
window.clearInterval = function(id) { delete window.testTimers[id]; nativeClearInterval(id); };
document.addEventListener('DOMContentLoaded', function() {
  var v = document.getElementById('video'), position = 60, paused = true;
  var tracks = [{language:'eng', enabled:true}, {language:'ita', enabled:false}];
  Object.defineProperties(v, {
    duration:{get:function(){return 600;}},
    paused:{get:function(){return paused;}},
    audioTracks:{get:function(){return tracks;}},
    currentTime:{get:function(){return position;},set:function(t){
      position=t; window.testSeeks.push(t);
      setTimeout(function(){if(v.onseeked){v.onseeked();}},0);
    }}
  });
  v.play = function(){paused=false; if(v.onplaying){v.onplaying();}};
  v.pause = function(){paused=true; if(v.onpause){v.onpause();}};
  v.load = function(){if(v.hasAttribute('src') && v.onloadedmetadata){v.onloadedmetadata();}};
});
"""

class Fixture:
    def __init__(self):
        self.calls = []
        self.delay_catalog = False
        self.delay_streams = False
        self.native_commands = []

    async def route(self, route):
        u = route.request.url
        if u.startswith(APP_URL):
            if u.endswith('/__native'):
                payload = route.request.post_data
                self.native_commands.append(json.loads(payload)['cmd'])
                binary = os.environ.get('STREAMLITE_CORE', str(ROOT / 'native/target/release/streamlite-core'))
                process = await asyncio.create_subprocess_exec(binary, stdin=asyncio.subprocess.PIPE,
                                                              stdout=asyncio.subprocess.PIPE)
                output, _ = await asyncio.wait_for(process.communicate(payload.encode()), timeout=4)
                return await route.fulfill(status=200, content_type='application/json', body=output)
            if u.endswith('/config.js'):
                config = APP_DIR / 'config.js'
                return await route.fulfill(status=200, content_type='application/javascript',
                                           body=(config if config.exists() else APP_DIR / 'config.example.js').read_text())
            return await route.continue_()
        self.calls.append(u)
        p = urlparse(u)
        q = parse_qs(p.query)
        async def reply(data):
            await route.fulfill(status=200, content_type='application/json',
                                headers={'Access-Control-Allow-Origin': '*'}, body=json.dumps(data))
        if p.hostname == 'api.strem.io':
            if p.path.endswith('login'):
                return await reply({'result': {'authKey': 'TEST'}})
            if p.path.endswith('addonCollectionGet'):
                return await reply({'result': {'addons': ADDONS}})
            if p.path.endswith('datastoreGet'):
                return await reply({'result': []})
        if '/catalog/' in p.path:
            if self.delay_catalog:
                await asyncio.sleep(0.4)
            kind = p.path.split('/')[2]
            return await reply({'metas': [{'id': f'tt{i + (1000 if kind == "movie" else 5000)}',
                                          'type': kind, 'name': f'{kind} {i}',
                                          'poster': f'https://images.example/{kind}{i}.png'} for i in range(100)]})
        if '/meta/' in p.path:
            kind = p.path.split('/')[2]
            ident = p.path.split('/')[-1].replace('.json', '')
            return await reply({'meta': {'id': ident, 'type': kind, 'name': 'Titolo di prova',
                                        'description': 'Descrizione di prova.',
                                        'background': 'https://images.example/BACKDROP.png',
                                        'logo': 'https://images.example/LOGO.png',
                                        'imdbRating': '8.1', 'videos': [
                                            {'id': f'{ident}:1:{i}', 'season': 1, 'episode': i,
                                             'title': f'Episodio {i}'} for i in range(1, 5)]}})
        if '/stream/' in p.path:
            if self.delay_streams:
                await asyncio.sleep(0.4)
            return await reply({'streams': STREAMS})
        if '/subtitles/' in p.path:
            return await reply({'subtitles': [
                {'lang': 'eng', 'url': 'https://subs.example/en.srt'},
                {'lang': 'ita', 'url': 'https://subs.example/it.srt'}]})
        if p.hostname == 'subs.example':
            return await route.fulfill(status=200, headers={'Access-Control-Allow-Origin': '*'},
                                       body='1\n00:00:01,000 --> 00:09:00,000\nCittà e caffè\n'.encode('cp1252'))
        if p.hostname == 'api.themoviedb.org':
            path = p.path.removeprefix('/3')
            if re.match(r'/tv/\d+/season/\d+$', path):
                return await reply({'episodes': [{'episode_number': i, 'name': f'Episodio {i}',
                                                  'air_date': '2020-01-01'} for i in range(1, 5)]})
            if re.match(r'/(movie|tv)/\d+$', path):
                kind, tid = path.strip('/').split('/')
                return await reply({'id': int(tid), 'title': 'Film di prova', 'name': 'Serie di prova',
                                    'imdb_id': f'tt{tid}', 'external_ids': {'imdb_id': f'tt{tid}'},
                                    'overview': 'Una descrizione italiana.', 'vote_average': 8.5,
                                    'runtime': 100, 'number_of_seasons': 1,
                                    'seasons': [{'season_number': 1, 'episode_count': 4}],
                                    'backdrop_path': '/BACKDROP.png', 'images': {'logos': []}})
            page = int(q.get('page', ['1'])[0])
            base = 5000 if '/tv' in path else 1000
            return await reply({'page': page, 'total_pages': 100, 'total_results': 2000,
                                'results': [{'id': base + (page - 1)*20 + i, 'title': f'Film {i}',
                                             'name': f'Serie {i}', 'poster_path': '/p.png'} for i in range(20)]})
        if p.hostname == 'www.omdbapi.com':
            return await reply({'Response': 'True', 'imdbRating': '8.1', 'Ratings': []})
        if p.hostname in ['images.example', 'image.tmdb.org']:
            return await route.fulfill(status=200, content_type='image/png', body=POSTER)
        # No real network or playback is used by this suite.
        await route.fulfill(status=404, headers={'Access-Control-Allow-Origin': '*'}, body='')

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fixture = Fixture()
    async with async_playwright() as p:
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        browser = await p.chromium.launch(**({'executable_path': executable} if executable else {}))
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        await context.add_init_script(MEDIA_STUB)
        if '--native' in sys.argv:
            await context.add_init_script("""
window.PalmServiceBridge = function() {};
window.PalmServiceBridge.prototype.call = function(uri, payload) {
  var bridge=this, xhr=new XMLHttpRequest(); this.xhr=xhr;
  xhr.open('POST','/__native');
  xhr.onload=function(){if(bridge.onservicecallback){bridge.onservicecallback(xhr.responseText);}};
  xhr.send(payload);
};
window.PalmServiceBridge.prototype.cancel = function(){if(this.xhr){this.xhr.abort();}};
""")
        await context.route('**/*', fixture.route)
        pg = await context.new_page()
        errors = []
        pg.on('pageerror', lambda error: errors.append(str(error)))
        await pg.goto(APP_URL + '/index.html')
        await expect(pg.locator('#screen-login')).to_be_visible()
        await pg.locator('#login-btn').click()
        await expect(pg.locator('#login-msg')).to_have_text('Inserisci email e password.')
        await pg.locator('#login-email').fill('test@example.com')
        await pg.locator('#login-pass').fill('test')
        await pg.keyboard.press('Enter')
        await pg.keyboard.press('Enter')
        await expect(pg.locator('#screen-home .card').first).to_be_visible()
        assert await pg.locator('#home-rows .row').count() <= 6
        assert await pg.locator('#home-rows .row').first.locator('.card').count() == 48
        assert not any('themoviedb' in call for call in fixture.calls), 'TMDB must be optional'
        print('PASS login, optional metadata, catalog cap')

        async def tab(name):
            await pg.locator(f'.screen.active [data-tab="{name}"]').click()
            await expect(pg.locator(f'#screen-{name}')).to_be_visible()

        # Late catalog replies must not rebuild a hidden tab or steal focus.
        fixture.delay_catalog = True
        await tab('movies')
        await tab('series')
        await pg.wait_for_timeout(650)
        assert await pg.locator('#movies-rows .card').count() == 0
        assert await pg.locator('#home-rows .card').count() == 0
        assert await pg.evaluate('document.querySelector(".screen.active").contains(window.__ls.focused())')
        fixture.delay_catalog = False
        for name in ['home', 'movies', 'series', 'home']:
            await tab(name)
            await expect(pg.locator(f'#{name}-rows .card').first).to_be_visible()
            assert await pg.locator('.screen:not(.active) .rows .card').count() == 0
        assert await pg.locator('.card img[src]').count() <= 36
        print('PASS tab cleanup, lazy images, stale catalog replies')

        # Keyboard moves through posters and restores focus after Back.
        await pg.mouse.move(1900, 10)
        for _ in range(12):
            await pg.keyboard.press('ArrowRight')
        focused_name = await pg.evaluate('window.__ls.focused().textContent')
        await pg.keyboard.press('Enter')
        await expect(pg.locator('#screen-detail')).to_be_visible()
        await expect(pg.locator('#detail-title')).to_have_text('Titolo di prova')
        assert not any('BACKDROP' in c or 'LOGO' in c for c in fixture.calls)
        await pg.keyboard.press('Escape')
        assert await pg.evaluate('window.__ls.focused().textContent') == focused_name
        await pg.keyboard.press('Enter')
        await expect(pg.locator('#screen-detail')).to_be_visible()
        await expect(pg.locator('#detail-title')).to_have_text('Titolo di prova')
        await pg.keyboard.press('ArrowRight')
        await pg.keyboard.press('Enter')
        await expect(pg.locator('#detail-actions')).to_contain_text('Nella lista')
        await pg.keyboard.press('Escape')
        assert await pg.evaluate('document.querySelector(".screen.active").contains(window.__ls.focused())')
        # Updating the watchlist rebuilds Home asynchronously; wait for a real
        # card instead of pressing OK while its navigation bar is still focused.
        await pg.locator('#home-rows .card').first.click()
        await expect(pg.locator('#screen-detail')).to_be_visible()
        await expect(pg.locator('#detail-actions .btn').first).to_have_text('▶ Guarda')
        await pg.mouse.move(1900, 10)
        await pg.keyboard.press('Enter')
        await expect(pg.locator('#streams-list .stream')).to_have_count(2)
        assert 'Italiano' in await pg.locator('#streams-list .stream').first.inner_text()
        await pg.locator('#streams-toggle').click()
        await expect(pg.locator('#streams-list .stream')).to_have_count(4)
        await pg.locator('#streams-toggle').click()
        await pg.locator('#streams-list .stream').first.click()
        await expect(pg.locator('#screen-player')).to_be_visible()
        await expect(pg.locator('#osd-audio')).to_contain_text('Italiano')
        await expect(pg.locator('#osd-sub')).to_contain_text('disattivati')
        assert 200 not in await pg.evaluate('Object.values(window.testTimers)')
        assert await pg.evaluate('document.getElementById("video").audioTracks[1].enabled')
        print('PASS remote navigation, watchlist, source filtering, Italian audio')

        # Rapid remote seeks produce one real seek, after 900 ms.
        await pg.keyboard.press('ArrowRight')
        await pg.keyboard.press('ArrowRight')
        assert await pg.evaluate('window.testSeeks.length') == 0
        await pg.wait_for_function('window.testSeeks.length === 1')
        assert await pg.evaluate('document.getElementById("video").currentTime') == 80
        await pg.evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{keyCode:405,bubbles:true}))')
        await expect(pg.locator('#osd-sub')).to_contain_text('Italiano')
        await expect(pg.locator('#subtitle')).to_have_text('Città e caffè')
        assert 200 in await pg.evaluate('Object.values(window.testTimers)')
        await pg.evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{keyCode:461,bubbles:true}))')
        await expect(pg.locator('#screen-streams')).to_be_visible()
        assert not await pg.locator('#video').get_attribute('src')
        assert await pg.evaluate('Object.keys(window.testTimers).length') == 0
        assert (await pg.evaluate('JSON.parse(localStorage.getItem("progress"))'))
        print('PASS deferred seek, Italian subtitles, player cleanup, progress')
        await pg.keyboard.press('Escape')
        await pg.keyboard.press('Escape')
        await expect(pg.locator('#screen-home')).to_be_visible()

        # A stream response arriving after Back must not steal focus.
        await pg.locator('#home-rows .card').first.click()
        fixture.delay_streams = True
        await pg.locator('#detail-actions .btn').first.click()
        await pg.keyboard.press('Escape')
        await pg.wait_for_timeout(600)
        assert await pg.evaluate('document.querySelector(".screen.active").contains(window.__ls.focused())')
        fixture.delay_streams = False
        await pg.keyboard.press('Escape')
        await tab('settings')
        await pg.locator('#set-tmdb').fill('TEST_TMDB')
        await pg.keyboard.press('Enter')
        await pg.keyboard.press('Enter')
        await tab('movies')
        await expect(pg.locator('#movies-rows .card').first).to_be_visible()
        assert await pg.locator('#movies-rows .row').count() <= 6
        # Trigger paging through the remote; the row must stop at 48 titles.
        await pg.locator('#movies-rows .card').first.click()
        await expect(pg.locator('#detail-title')).to_have_text('Film di prova')
        await pg.keyboard.press('Escape')
        for _ in range(52):
            await pg.keyboard.press('ArrowRight')
            await pg.wait_for_timeout(10)
        assert await pg.locator('#movies-rows .row').first.locator('.card').count() == 48
        tmdb_calls = [c for c in fixture.calls if 'api.themoviedb.org' in c]
        assert all(parse_qs(urlparse(c).query).get('language') in [['it-IT'], ['en-US']] for c in tmdb_calls)
        assert not any('credits' in c or 'recommendations' in c or 'images,' in c for c in tmdb_calls)
        await pg.screenshot(path=str(OUT / 'streamlite-home.png'))
        print('PASS stale streams, Italian metadata, paging cap, no visual extras')

        await tab('series')
        await pg.locator('#series-rows .card').first.click()
        await expect(pg.locator('#detail-episodes .ep')).to_have_count(4)
        await pg.locator('#detail-episodes .ep').nth(1).click()
        await expect(pg.locator('#streams-list .stream').first).to_be_visible()
        assert any('/stream/series/tt5000%3A1%3A2.json' in c for c in fixture.calls)
        await pg.keyboard.press('Escape')
        await pg.keyboard.press('Escape')
        await tab('settings')
        await pg.locator('#set-logout').click()
        await expect(pg.locator('#screen-login')).to_be_visible()
        assert await pg.locator('.rows .card').count() == 0
        assert await pg.evaluate('localStorage.getItem("auth")') is None
        assert not errors, errors
        if '--native' in sys.argv:
            assert {'health','catalog','analyzeStreams','parseSubtitles'}.issubset(set(fixture.native_commands))
            print('PASS actual Rust binary used through simulated Luna bridge')
        print('PASS episodes, logout, no JavaScript errors')
        await browser.close()

if __name__ == '__main__':
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(APP_DIR)))
    APP_URL = f'http://127.0.0.1:{server.server_port}'
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        asyncio.run(main())
    finally:
        server.shutdown()
