use serde::Deserialize;
use tauri::Manager;

#[derive(Deserialize)]
struct SessionCookie {
    name: String,
    value: String,
    domain: Option<String>,
    path: Option<String>,
    expires: Option<f64>,
    #[serde(rename = "sameSite")]
    same_site: Option<String>,
    #[serde(rename = "httpOnly", default)]
    http_only: bool,
    #[serde(default)]
    secure: bool,
}

/// Mo WebviewWindow moi voi session AA da duoc inject vao WebView2 CookieManager.
/// HTTP-only cookies duoc set o tang engine (khong qua JS) => dang nhap thanh cong.
///
/// Khong rely vao shared cookie store giua cac window nua.
/// Tao chinh AA window bang route noi bo cua app, doi webview init xong,
/// inject cookie vao CHINH webview do, roi Navigate() cung instance do sang AA.
#[tauri::command]
async fn open_aa_session(app: tauri::AppHandle, session_json: String) -> Result<(), String> {
    let session: serde_json::Value =
        serde_json::from_str(&session_json).map_err(|e| e.to_string())?;

    let cookies: Vec<SessionCookie> = session["cookies"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|c| {
            c["domain"]
                .as_str()
                .unwrap_or("")
                .contains("artificialanalysis")
        })
        .filter_map(|c| serde_json::from_value(c).ok())
        .collect();

    eprintln!("[AA] got {} AA cookies to inject", cookies.len());
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    eprintln!("[AA] building internal bootstrap window...");
    let win = tauri::WebviewWindowBuilder::new(
        &app,
        format!("aa-{ts}"),
        tauri::WebviewUrl::App("/aa-web".into()),
    )
    .title("Artificial Analysis \u{2014} Image Lab")
    .inner_size(1400.0, 900.0)
    .resizable(true)
    .build()
    .map_err(|e| e.to_string())?;

    #[cfg(debug_assertions)]
    win.open_devtools();

    let app_handle = app.clone();
    let window_label = win.label().to_string();
    eprintln!("[AA] bootstrap window built: {window_label}");
    eprintln!("[AA] spawning delayed injection task...");

    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        eprintln!("[AA] delayed task awake for {window_label}");

        let Some(win) = app_handle.get_webview_window(&window_label) else {
            eprintln!("[AA] FAILED: aa window not found after delay: {window_label}");
            return;
        };

        if let Err(err) = win.with_webview(move |wv: tauri::webview::PlatformWebview| {
            eprintln!("[AA] with_webview callback ENTERED (aa window after delay)");

            let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> Result<(), String> {
                #[cfg(windows)]
                {
                    use webview2_com::Microsoft::Web::WebView2::Win32::{ICoreWebView2, ICoreWebView2_2};
                    use webview2_com_sys::Microsoft::Web::WebView2::Win32::COREWEBVIEW2_COOKIE_SAME_SITE_KIND_LAX;
                    use webview2_com_sys::Microsoft::Web::WebView2::Win32::COREWEBVIEW2_COOKIE_SAME_SITE_KIND_NONE;
                    use webview2_com_sys::Microsoft::Web::WebView2::Win32::COREWEBVIEW2_COOKIE_SAME_SITE_KIND_STRICT;
                    use windows::core::{Interface, HSTRING};

                    unsafe {
                        let wv2: ICoreWebView2 = wv.controller().CoreWebView2()
                            .map_err(|e| format!("CoreWebView2() failed: {e}"))?;
                        let wv2_2: ICoreWebView2_2 = wv2.cast()
                            .map_err(|e| format!("cast ICoreWebView2_2 failed: {e}"))?;
                        let cookie_mgr = wv2_2.CookieManager()
                            .map_err(|e| format!("CookieManager() failed: {e}"))?;

                        for c in &cookies {
                            let domain = c.domain.as_deref().unwrap_or(".artificialanalysis.ai");
                            let path = c.path.as_deref().unwrap_or("/");
                            eprintln!(
                                "[AA] inject cookie: {} @ {} path={} secure={} httpOnly={} sameSite={:?}",
                                c.name,
                                domain,
                                path,
                                c.secure,
                                c.http_only,
                                c.same_site
                            );

                            let cookie = cookie_mgr.CreateCookie(
                                &HSTRING::from(c.name.as_str()),
                                &HSTRING::from(c.value.as_str()),
                                &HSTRING::from(domain),
                                &HSTRING::from(path),
                            ).map_err(|e| format!("CreateCookie '{}' failed: {e}", c.name))?;
                            cookie.SetIsHttpOnly(c.http_only)
                                .map_err(|e| format!("SetIsHttpOnly failed: {e}"))?;
                            cookie.SetIsSecure(c.secure)
                                .map_err(|e| format!("SetIsSecure failed: {e}"))?;
                            if let Some(same_site) = c.same_site.as_deref() {
                                let same_site_kind = match same_site.to_ascii_lowercase().as_str() {
                                    "lax" => COREWEBVIEW2_COOKIE_SAME_SITE_KIND_LAX,
                                    "strict" => COREWEBVIEW2_COOKIE_SAME_SITE_KIND_STRICT,
                                    "none" => COREWEBVIEW2_COOKIE_SAME_SITE_KIND_NONE,
                                    other => return Err(format!("Unsupported sameSite value: {other}")),
                                };
                                cookie.SetSameSite(same_site_kind)
                                    .map_err(|e| format!("SetSameSite failed: {e}"))?;
                            }
                            if let Some(exp) = c.expires {
                                if exp > 0.0 {
                                    cookie.SetExpires(exp)
                                        .map_err(|e| format!("SetExpires failed: {e}"))?;
                                }
                            }
                            cookie_mgr.AddOrUpdateCookie(&cookie)
                                .map_err(|e| format!("AddOrUpdateCookie '{}' failed: {e}", c.name))?;
                        }

                        eprintln!("[AA] all cookies injected into AA window store");
                        eprintln!("[AA] navigating same AA webview instance...");
                        wv2.Navigate(&HSTRING::from("https://artificialanalysis.ai/image/image-lab"))
                            .map_err(|e| format!("Navigate() failed: {e}"))?;
                        eprintln!("[AA] Navigate() called OK");
                        Ok(())
                    }
                }

                #[cfg(not(windows))]
                Err("Cookie injection chi ho tro Windows".into())
            }))
            .unwrap_or_else(|_| {
                eprintln!("[AA] PANIC in with_webview callback");
                Err("with_webview callback panicked".into())
            });

            if let Err(ref e) = result {
                eprintln!("[AA] FAILED: {e}");
            } else {
                eprintln!("[AA] callback finished successfully");
            }
        }) {
            eprintln!("[AA] FAILED: scheduling delayed with_webview callback: {err}");
        } else {
            eprintln!("[AA] delayed with_webview callback scheduled OK");
        }
    });

    eprintln!("[AA] command returning immediately; delayed task will inject cookies");
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![open_aa_session])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
