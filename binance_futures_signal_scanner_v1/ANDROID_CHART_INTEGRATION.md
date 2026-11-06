# Android Chart WebView Integration

The repository currently contains the backend and a reusable chart asset; it does not contain the Android application module. Copy:

`binance_futures_signal_scanner_v1/android_assets/chart_webview.html`

to the Android app module at:

`app/src/main/assets/chart_webview.html`

The asset loads TradingView Lightweight Charts 4.2.2 from the pinned HTTPS CDN. The device therefore needs internet access for the chart library. Market candles and indicators should be fetched by the Android app from the CUAN Scanner API, then passed into the page; the HTML does not contain API credentials and does not call the API directly.

## WebView setup (Kotlin)

```kotlin
webView.settings.javaScriptEnabled = true
webView.settings.domStorageEnabled = true
webView.addJavascriptInterface(object {
    @android.webkit.JavascriptInterface
    fun onIntervalChange(interval: String) {
        // Dispatch to your ViewModel/API client to fetch the selected interval.
        // Example: viewModel.loadChart(symbol, interval)
    }
}, "AndroidChartBridge")
webView.webViewClient = object : android.webkit.WebViewClient() {
    override fun onPageFinished(view: android.webkit.WebView, url: String) {
        view.evaluateJavascript(
            "window.CuanChart && window.CuanChart.onIntervalChange(function(interval) { AndroidChartBridge.onIntervalChange(interval); })",
            null
        )
    }
}
webView.loadUrl("file:///android_asset/chart_webview.html")
```

Add the Android INTERNET permission if it is not already present:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

## Send chart data from Android

After the app receives the JSON response from:

`GET /market/chart/BTCUSDT?interval=15&limit=500`

pass the response JSON directly to the JavaScript chart API. Use your JSON library's safe JSON serialization; do not manually concatenate untrusted strings.

```kotlin
val chartJson = responseBodyString // validated JSON from your API client
webView.post {
    webView.evaluateJavascript(
        "window.CuanChart && window.CuanChart.setData($chartJson)",
        null
    )
}
```

For signal levels, pass the selected signal's Entry, SL, and TP fields:

```kotlin
val levelsJson = """{"entry": 68000, "sl": 67500, "tp1": 69000, "tp2": 69500, "tp3": 70000}"""
webView.post {
    webView.evaluateJavascript(
        "window.CuanChart && window.CuanChart.setSignalLevels($levelsJson)",
        null
    )
}
```

## Timeframe buttons

The chart asset calls an optional JavaScript callback when a timeframe button is tapped. Connect it to the Android data layer and request the same endpoint with the selected Bybit interval:

```javascript
// Already wired in the Kotlin WebViewClient example above. The native bridge
// should fetch /market/chart/{symbol}?interval={interval} and call setData().
```

Supported interval values: `1`, `5`, `15`, `60`, `240`, and `D`.

## Important notes

- The chart API returns closed candles only.
- EMA 9/21/20/50, ATR 14, market structure, FVG and pivot S/R are computed by the backend.
- The current chart asset draws FVG boundaries as horizontal levels; shaded FVG rectangles and draggable drawings are not implemented yet.
- Entry/SL/TP lines are shown only after Android calls `setSignalLevels`.
- Avoid enabling unrestricted file-URL access in WebView. Use the native API client to retrieve data and pass validated JSON into the chart.
