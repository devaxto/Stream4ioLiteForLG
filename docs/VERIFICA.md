# Verifica di StreamLite 1.3.0

Ambiente di verifica: Linux x86_64, Rust 1.85.1, Chromium headless moderno e QEMU user-mode ARMv7. La TV LG fisica non è collegata a questo ambiente.

## Risultati automatizzati

- Sei test Rust superati sull’host e sei sul target ARMv7 con `arm-asm` abilitato.
- Il binario ARM release esegue `--self-test` sotto QEMU e restituisce `armAsm: true`.
- Routine Assembly controllata per ogni byte e ogni lunghezza 0–256; nessuna modifica oltre la slice.
- Il servizio avvia davvero un worker Rust: protocollo, allowlist, payload massimo, errore di spawn e rifiuto della concorrenza verificati.
- Flussi browser verificati con e senza Rust reale; API, Luna e media sono simulati. Nessuna chiave o credenziale reale è stata usata.
- I flussi del browser sono provati anche sui file minificati estratti dall’IPK effettivo.
- Il pacchetto è controllato dopo la build: ELF32 ARM EABI5 hard-float statico, privo di interprete dinamico e con permessi eseguibili. Hash e dimensioni effettive in `dist/verification.json`.

Pacchetto verificato: circa 301 KiB. Core ARM statico: 514.240 byte. I valori precisi e gli hash sono generati insieme all’IPK.

## Da provare sul televisore

1. Rilevare codice modello LG e versione effettiva di webOS: “3.16” potrebbe essere il firmware.
2. Installare l’IPK tramite Developer Mode e Dev Manager.
3. Controllare in Impostazioni lo stato `Rust nativo ARM + Assembly ARM`; verificare il log col tasto blu.
4. Accedere a Stremio e verificare un catalogo, una ricerca e un episodio.
5. Provare un file HTTP H.264/AAC, poi pause, seek ripetuti, sottotitoli e Indietro.
6. Misurare avvio, RAM totale e fluidità durante l’uso reale. Il peso dell’IPK non misura la memoria del browser o del servizio Node.

Non sono stati misurati FPS, tempi di avvio o guadagni di prestazione dell’Assembly sulla TV. Non viene dichiarata compatibilità hardware certificata.
