mod ascii;
use serde_json::{json, Value};
use std::collections::HashSet;

pub const MAX_INPUT: usize = 2 * 1024 * 1024;
pub const MAX_STREAMS: usize = 120;
pub const MAX_CUES: usize = 10_000;
pub fn asm_enabled() -> bool {
    cfg!(all(target_arch = "arm", feature = "arm-asm"))
}
pub fn self_test() -> bool {
    ascii::self_test()
}
fn text<'a>(v: &'a Value, key: &str) -> &'a str {
    v.get(key).and_then(Value::as_str).unwrap_or("")
}
fn folded(s: &str) -> String {
    let mut bytes = s.as_bytes().to_vec();
    ascii::lower(&mut bytes);
    // ASCII case conversion cannot invalidate UTF-8.
    String::from_utf8(bytes).expect("ASCII folding preserves UTF-8")
}
fn token(s: &str, word: &str) -> bool {
    s.split(|c: char| !c.is_ascii_alphanumeric())
        .any(|part| part == word)
}
fn any(s: &str, needles: &[&str]) -> bool {
    needles.iter().any(|n| s.contains(n))
}
fn size_gb(s: &str) -> Option<f64> {
    let bytes = s.as_bytes();
    for (i, byte) in bytes.iter().enumerate() {
        if !byte.is_ascii_digit() {
            continue;
        }
        if i > 0 && bytes[i - 1].is_ascii_digit() {
            continue;
        }
        let mut end = i;
        while end < bytes.len() && (bytes[end].is_ascii_digit() || b".,".contains(&bytes[end])) {
            end += 1;
        }
        let number = s.get(i..end)?.replace(',', ".").parse::<f64>().ok();
        let unit = s.get(end..)?.trim_start();
        if let Some(n) = number {
            if unit.starts_with("gib") || unit.starts_with("gb") {
                return Some(n);
            }
            if unit.starts_with("mib") || unit.starts_with("mb") {
                return Some(n / 1024.0);
            }
        }
    }
    None
}

pub fn analyze_stream(s: &Value) -> Value {
    let hints = &s["behaviorHints"];
    let original = [
        text(s, "name"),
        text(s, "title"),
        text(s, "description"),
        text(hints, "filename"),
    ]
    .join(" ");
    let lower = folded(&original);
    let resolution = if any(&lower, &["2160p"]) || token(&lower, "4k") || token(&lower, "uhd") {
        2160
    } else if any(&lower, &["1080p", "1080i"]) || token(&lower, "fhd") {
        1080
    } else if lower.contains("720p") {
        720
    } else if any(&lower, &["480p", "576p"]) || token(&lower, "sd") {
        480
    } else {
        0
    };
    let size = hints["videoSize"]
        .as_f64()
        .filter(|n| *n > 0.0)
        .map(|n| n / 1073741824.0)
        .or_else(|| size_gb(&lower));
    let container = if token(&lower, "mp4") {
        "MP4"
    } else if token(&lower, "mkv") {
        "MKV"
    } else {
        ""
    };
    let mut reasons = Vec::new();
    let url = folded(text(s, "url"));
    if !(url.starts_with("https://") || url.starts_with("http://")) {
        reasons.push(if s["infoHash"].is_string() {
            "Torrent senza link HTTP"
        } else {
            "Nessun link HTTP"
        });
    }
    if resolution == 2160 {
        reasons.push("4K");
    }
    if ["x265", "h265", "hevc"].iter().any(|w| token(&lower, w)) || any(&lower, &["x.265", "h.265"])
    {
        reasons.push("HEVC/x265");
    }
    if token(&lower, "av1") {
        reasons.push("AV1");
    }
    if ["hdr", "hdr10", "hdr10plus", "dovi", "dv"]
        .iter()
        .any(|w| token(&lower, w))
        || any(&lower, &["dolby vision", "dolbyvision"])
    {
        reasons.push("HDR/DV");
    }
    if any(&lower, &["10bit", "10-bit", "10 bit", "hi10"]) {
        reasons.push("10bit");
    }
    if any(&lower, &["dts", "truehd", "atmos"]) {
        reasons.push("Audio DTS/TrueHD");
    }
    if lower.contains("remux") {
        reasons.push("Remux pesante");
    }
    if token(&lower, "3d") || token(&lower, "sbs") {
        reasons.push("3D");
    }
    if any(&lower, &[" download]", "uncached", "not cached", "⏳"]) {
        reasons.push("Non in cache");
    }
    if size.is_some_and(|n| n > 12.0) {
        reasons.push("File troppo grande");
    }
    let italian = lower.contains("🇮🇹")
        || ["italian", "italiano", "ita", "it"]
            .iter()
            .any(|w| token(&lower, w));
    let multi = token(&lower, "dual") || token(&lower, "multi");
    let mut tags: Vec<String> = Vec::new();
    if italian {
        tags.push("AUDIO IT".into());
    } else if multi {
        tags.push("Audio multiplo".into());
    }
    if resolution > 0 {
        tags.push(if resolution == 2160 {
            "4K".into()
        } else {
            format!("{resolution}p")
        });
    }
    if let Some(n) = size {
        tags.push(format!("{n:.1} GB"));
    }
    if !container.is_empty() {
        tags.push(container.into());
    }
    let h264 = ["x264", "h264", "avc"].iter().any(|w| token(&lower, w))
        || any(&lower, &["x.264", "h.264"]);
    if h264 {
        tags.push("x264".into());
    }
    if token(&lower, "aac") {
        tags.push("AAC".into());
    } else if ["ac3", "dd5", "ddp", "eac3"]
        .iter()
        .any(|w| token(&lower, w))
        || lower.contains("dd+")
    {
        tags.push("AC3".into());
    }
    if any(&lower, &["[rd+]", "⚡", "cached"]) && !reasons.contains(&"Non in cache") {
        tags.push("⚡".into());
    }
    let mut score = if italian {
        1000
    } else if multi {
        150
    } else {
        0
    };
    score += match resolution {
        1080 => 300,
        720 => 200,
        480 => 50,
        _ => 100,
    };
    if container == "MP4" {
        score += 30;
    }
    if h264 {
        score += 40;
    }
    if let Some(n) = size {
        if n > 8.0 {
            score -= 80;
        } else if n > 5.0 {
            score -= 30;
        }
    }
    json!({"res":resolution,"size":size,"container":container,"reasons":reasons,"tags":tags,
           "italian":italian,"multiAudio":multi,"ok":reasons.is_empty(),"score":score,"text":original})
}

fn timestamp(s: &str) -> Option<f64> {
    let s = s.split_whitespace().next()?.replace(',', ".");
    let mut parts: Vec<&str> = s.split(':').collect();
    if parts.len() < 2 || parts.len() > 3 {
        return None;
    }
    let seconds = parts.pop()?.parse::<f64>().ok()?;
    let minutes = parts.pop()?.parse::<u32>().ok()?;
    let hours = if let Some(h) = parts.pop() {
        h.parse::<u32>().ok()?
    } else {
        0
    };
    if !seconds.is_finite() || !(0.0..60.0).contains(&seconds) || minutes >= 60 {
        return None;
    }
    Some(hours as f64 * 3600.0 + minutes as f64 * 60.0 + seconds)
}
fn subtitle_body(s: &str) -> String {
    // Keep formatting tags supported by the UI. Everything else is removed.
    let mut out = String::new();
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '<' {
            let mut tag = String::new();
            for next in chars.by_ref() {
                if next == '>' {
                    break;
                }
                tag.push(next);
            }
            if ["i", "/i", "b", "/b", "u", "/u"].contains(&tag.to_ascii_lowercase().as_str()) {
                out.push('<');
                out.push_str(&tag);
                out.push('>');
            }
        } else {
            out.push(c);
        }
        if out.len() > 4096 {
            break;
        }
    }
    out
}
pub fn parse_subtitles(input: &str) -> Value {
    let normalized = input
        .trim_start_matches('\u{feff}')
        .replace("\r\n", "\n")
        .replace('\r', "\n");
    let mut cues = Vec::new();
    for block in normalized.split("\n\n") {
        let mut lines = block.lines();
        while let Some(line) = lines.next() {
            if let Some((a, b)) = line.split_once("-->") {
                if let (Some(start), Some(end)) = (timestamp(a), timestamp(b)) {
                    let body = subtitle_body(&lines.collect::<Vec<_>>().join("\n"));
                    if end > start && !body.trim().is_empty() {
                        cues.push((start, end, body));
                    }
                }
                break;
            }
        }
        if cues.len() >= MAX_CUES {
            break;
        }
    }
    cues.sort_by(|a, b| a.0.total_cmp(&b.0));
    Value::Array(
        cues.into_iter()
            .map(|(s, e, t)| json!({"s":s,"e":e,"t":t}))
            .collect(),
    )
}
pub fn dispatch(request: &Value) -> Result<Value, &'static str> {
    match text(request, "cmd") {
        "health" => Ok(json!({"version":"1.3.0","engine":"rust-native","armAsm":asm_enabled()})),
        "analyzeStreams" => {
            let streams = request["streams"]
                .as_array()
                .ok_or("streams must be an array")?;
            Ok(Value::Array(
                streams
                    .iter()
                    .filter(|s| s.is_object())
                    .take(MAX_STREAMS)
                    .map(|s| json!({"s":s,"info":analyze_stream(s)}))
                    .collect(),
            ))
        }
        "parseSubtitles" => Ok(parse_subtitles(text(request, "text"))),
        "catalog" => {
            let metas = request["metas"]
                .as_array()
                .ok_or("metas must be an array")?;
            let mut seen = HashSet::new();
            Ok(Value::Array(
                metas
                    .iter()
                    .filter(|m| !text(m, "id").is_empty() && seen.insert(text(m, "id")))
                    .take(48)
                    .cloned()
                    .collect(),
            ))
        }
        _ => Err("unknown command"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ascii_all_bytes_and_lengths() {
        assert!(self_test());
    }
    #[test]
    fn italian_safe_source() {
        let x = analyze_stream(
            &json!({"title":"Film.1080p.ITA.x264.AAC.mp4 2,3 GB","url":"https://test/video"}),
        );
        assert_eq!(x["italian"], true);
        assert_eq!(x["ok"], true);
        assert_eq!(x["size"], 2.3);
        assert_eq!(x["score"], 1370);
    }
    #[test]
    fn codec_and_transport_filter() {
        let x =
            analyze_stream(&json!({"title":"Film.2160p.HDR.x265.DTS.mkv 25GB","infoHash":"abc"}));
        assert_eq!(x["ok"], false);
        assert_eq!(x["reasons"].as_array().unwrap().len(), 6);
        assert!(analyze_stream(&json!({"url":"file:///etc/passwd"}))["ok"] == false);
    }
    #[test]
    fn no_false_italian_inside_title() {
        assert_eq!(
            analyze_stream(&json!({"title":"Capital Theory 1080p","url":"https://x"}))["italian"],
            false
        );
    }
    #[test]
    fn srt_and_vtt_are_sorted_and_sanitized() {
        let cues=parse_subtitles("WEBVTT\n\n00:00:04.000 --> 00:00:05.000 align:start\n<script>bad</script><b>Città</b>\n\n1\n00:00:01,000 --> 00:00:03,000\nCaffè\n");
        assert_eq!(cues[0]["s"], 1.0);
        assert_eq!(cues[1]["t"], "bad<b>Città</b>");
        assert_eq!(parse_subtitles("1\n00:00:05 --> 00:00:01\nbad"), json!([]));
    }
    #[test]
    fn hard_limits_and_catalog_deduplication() {
        let streams: Vec<_> = (0..500)
            .map(|i| json!({"url":format!("https://x/{i}")}))
            .collect();
        assert_eq!(
            dispatch(&json!({"cmd":"analyzeStreams","streams":streams}))
                .unwrap()
                .as_array()
                .unwrap()
                .len(),
            120
        );
        let metas: Vec<_> = (0..300)
            .map(|i| json!({"id":format!("tt{}",i/2)}))
            .collect();
        assert_eq!(
            dispatch(&json!({"cmd":"catalog","metas":metas}))
                .unwrap()
                .as_array()
                .unwrap()
                .len(),
            48
        );
        assert!(dispatch(&json!({"cmd":"shell"})).is_err());
    }
}
