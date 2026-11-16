# StreamLite per LG webOS 2018

Client non ufficiale compatibile con gli addon Stremio: **core Rust nativo ARMv7, routine Assembly ARM e interfaccia ES5 senza framework**. Il player è quello della TV. Nessun WebAssembly, React, motore torrent o decoder video incluso.

Fork di [LiteStream / webos-legacy-stremio](https://github.com/SinanKulen/webos-legacy-stremio), commit di partenza `3474601`. Non è un fork del motore ufficiale Stremio. La licenza MIT e i crediti originali sono conservati.

## Installazione

Scarica l’[IPK pronto dalla release GitHub](https://github.com/devaxto/Stream4ioLiteForLG/releases/tag/v1.3.0-webos2018). Nella stessa release trovi l’archivio dei sorgenti e i checksum SHA-256.

Il pacchetto è `dist/org.streamlite.webos_1.3.0_all.ipk`. Contiene il core **ARMv7**: il suffisso `all` è prodotto dal packager per l’app web con servizio JS e non indica compatibilità con altre CPU.

1. Sulla TV installa **Developer Mode** dallo store LG; accedi con il tuo account sviluppatore LG gratuito e abilita **Dev Mode Status** e **Key Server**.
2. Sul computer installa [webOS Dev Manager](https://github.com/webosbrew/dev-manager-desktop), aggiungi la TV usando IP e passphrase mostrati da Developer Mode.
3. In **Apps → Install**, seleziona il file `.ipk`. Avvia **StreamLite** sulla TV.
4. Accedi con il tuo account Stremio, sul quale devono essere già configurati gli addon. Le chiavi TMDB e OMDb sono facoltative e si inseriscono in **Impostazioni**.
5. In **Impostazioni**, la riga in basso indica **Rust nativo ARM + Assembly ARM** se il servizio è attivo. Il tasto blu mostra il log diagnostico. Se il firmware impedisce l’avvio del servizio viene usato il fallback ES5 e lo stato lo segnala.

Developer Mode ha una scadenza: rinnovala prima che termini per conservare le app installate. Non serve il root.

## Cosa include

- Login Stremio e lettura degli addon e della libreria; ricerca, film, serie ed episodi.
- Interfaccia italiana; preferenza per audio italiano e sottotitoli italiani, poi inglesi.
- Analisi sorgenti, normalizzazione cataloghi e parsing SRT/VTT eseguiti dal core Rust tramite un piccolo servizio Luna compatibile con Node 0.12.
- Routine Assembly ARMv7 per convertire le lettere ASCII in minuscolo durante l’analisi. Non richiede NEON e preserva i byte UTF-8. Esiste anche il percorso Rust equivalente.
- Lista personale e avanzamento salvati localmente; seek raggruppato dopo 900 ms; rilascio del video e dei timer all’uscita.

## Limiti per ridurre il consumo

| Risorsa | Limite |
|---|---:|
| Righe per schermata | 6 |
| Titoli per riga | 48 |
| Sorgenti complessive | 120 |
| Cache TMDB / OMDb | 24 elementi ciascuna |
| Richiesta al core / risposta dal servizio | 2 MiB |
| Cue sottotitoli | 10.000 |
| Worker Rust simultanei | 1, termina dopo ogni richiesta |
| Budget pacchetto IPK | 512 KiB |
| Budget binario Rust statico | 600 KiB |

Le schermate di catalogo vengono rilasciate al cambio di scheda. I poster vengono caricati vicino alla porzione visibile e scaricati quando lontani. Sfondi, loghi, gallerie cast, animazioni e filtri grafici sono rimossi. Il timer dei sottotitoli esiste solo quando ci sono sottotitoli attivi.

**Rust e Assembly non garantiscono automaticamente meno RAM o maggiore velocità.** Il core nativo aumenta il peso rispetto alla variante solo ES5; i budget e i limiti sopra sono controllati, mentre RAM totale e fluidità vanno misurate sulla TV.

## Compatibilità e riproduzione

L’interfaccia è limitata a ES5 per Chromium 38/53, usati da webOS 3.x/4.x. Il core è un eseguibile Linux ARMv7 hard-float con musl 1.2.3 collegata staticamente, così non dipende dalla versione di glibc della TV.

Il numero fornito, “3.16”, non identifica da solo modello e versione della piattaforma. **Questa build non è ancora stata provata sulla TV fisica**: restano da verificare l’avvio del servizio nel firmware esatto e i codec del televisore. Un browser moderno e QEMU non sostituiscono questa prova.

Il player accetta link HTTP/HTTPS diretti restituiti dagli addon. I torrent senza link diretto richiedono un servizio esterno. H.264 con AAC/AC3 a bitrate moderato è il punto di partenza consigliato. Le sorgenti pesanti vengono nascoste inizialmente; **Mostra tutte** le rende visibili. È un filtro prudente basato sulle descrizioni, non una verifica dei codec hardware. La selezione delle tracce audio dipende da `video.audioTracks`.

La lista personale e i nuovi progressi sono locali e non vengono sincronizzati verso Stremio. L’app non include addon o contenuti.

## Build riproducibile

Su Linux servono Node/npm, Python 3.10+, Rust tramite rustup e `ar` di GNU binutils.

```sh
npm ci
cd native
rustup show    # installa la toolchain e il target fissati in rust-toolchain.toml
cargo fetch --locked
rustup component add rustfmt clippy
cd ..
python -m pip install -r tests/requirements.txt
python -m playwright install chromium
npm run verify
```

`npm run build` produce l’IPK con Rust e Assembly. `npm run build:web` produce una variante senza servizio nativo in `dist/web-only/`. Entrambe le build distribuiscono una configurazione senza chiavi personali; `app/config.js` non viene incluso.

Per compilare il core senza Assembly:

```sh
cd native
cargo build --locked --release --target armv7-unknown-linux-musleabihf
```

La build del pacchetto usa esplicitamente `--features arm-asm`. `opt-level=z`, LTO, una sola unità di compilazione, simboli rimossi e `panic=abort` limitano il peso del binario.

## Verifiche

- Test Rust di codec, italiano, cataloghi, sottotitoli e limiti; eseguiti anche con **QEMU ARM e Assembly attivo**.
- Verifica Assembly su tutti i 256 byte e tutte le lunghezze di slice 0–256, inclusi i byte sentinella.
- Test del servizio con il binario Rust reale: protocollo, errore di avvio, dimensioni e concorrenza.
- Test Playwright con API simulate, sia in fallback sia con il binario Rust reale dietro un ponte Luna simulato: telecomando, Magic Remote, focus, sorgenti, audio, sottotitoli, seek, episodi, pulizia e logout. Il video è simulato: non prova la decodifica hardware.
- Parsing ES5 di tutti i file distribuiti; controllo dell’IPK reale, del tipo ELF ARM statico, dei permessi di esecuzione, delle licenze, dei budget e della corrispondenza coi sorgenti.

`dist/verification.json` contiene dimensioni e SHA-256. Lo stato dettagliato delle prove è in [docs/VERIFICA.md](docs/VERIFICA.md).

## Struttura e licenza

```text
app/                  interfaccia ES5 e player HTML5 della TV
native/               core Rust, Assembly ARM e lockfile Cargo
service/              piccolo ponte Luna → worker nativo, senza shell
scripts/              build, verifica ES5, licenze e verifica IPK
tests/                test browser e servizio; video e API simulati
```

[MIT](LICENSE), copyright originale Sinan Kulen. I componenti Rust e musl mantengono le rispettive licenze, incluse nel pacchetto. Progetto indipendente, non affiliato con Stremio o LG.
