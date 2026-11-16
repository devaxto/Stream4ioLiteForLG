use serde_json::{json, Value};
use std::io::{self, Read, Write};
fn main() {
    if std::env::args().nth(1).as_deref() == Some("--self-test") {
        if !streamlite_core::self_test() {
            std::process::exit(1);
        }
        println!(
            "{}",
            json!({"returnValue":true,"armAsm":streamlite_core::asm_enabled(),"test":"all bytes, all slice lengths"})
        );
        return;
    }
    let mut bytes = Vec::new();
    let result: Result<Value, String> = (|| {
        io::stdin()
            .take((streamlite_core::MAX_INPUT + 1) as u64)
            .read_to_end(&mut bytes)
            .map_err(|_| "stdin error")?;
        if bytes.len() > streamlite_core::MAX_INPUT {
            return Err("request too large".into());
        }
        let req: Value = serde_json::from_slice(&bytes).map_err(|_| "invalid JSON")?;
        streamlite_core::dispatch(&req).map_err(str::to_string)
    })();
    let response = match result {
        Ok(value) => json!({"returnValue":true,"result":value}),
        Err(error) => json!({"returnValue":false,"errorText":error}),
    };
    let stdout = io::stdout();
    let mut output = stdout.lock();
    if serde_json::to_writer(&mut output, &response).is_err() || output.write_all(b"\n").is_err() {
        std::process::exit(1);
    }
}
