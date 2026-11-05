package dev.alita.androidagent.zcode.runtime

import android.content.Intent
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import androidx.activity.ComponentActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Minimal Phase 4 bridge UI. The Node foreground service remains the protocol owner. */
class ZCodeActivity : ComponentActivity() {
    private lateinit var webView: WebView
    private var bridgeLoaded = false
    private var connecting = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ContextCompat.startForegroundService(this, Intent(this, ZCodeHostService::class.java))
        val token = ZCodeRuntimeBundle(this).bridgeToken()
        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView?, url: String?) {
                    bridgeLoaded = url?.startsWith("http://127.0.0.1:8765/") == true
                }

                override fun onReceivedError(view: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                    super.onReceivedError(view, request, error)
                    if (request?.isForMainFrame == true) {
                        bridgeLoaded = false
                        connectWhenReady(token)
                    }
                }
            }
        }
        setContentView(webView)
        connectWhenReady(token)
    }

    override fun onResume() {
        super.onResume()
        if (::webView.isInitialized && !bridgeLoaded) {
            connectWhenReady(ZCodeRuntimeBundle(this).bridgeToken())
        }
    }

    private fun connectWhenReady(token: String) {
        if (connecting) return
        connecting = true
        lifecycleScope.launch {
            try {
                repeat(120) {
                    val ready = runCatching { ZCodeGatewayClient(this@ZCodeActivity).status().optString("phase") == "ready" }
                        .getOrDefault(false)
                    if (ready) {
                        webView.loadUrl("http://127.0.0.1:8765/?t=$token")
                        return@launch
                    }
                    delay(500)
                }
            } finally {
                connecting = false
            }
        }
    }

    override fun onDestroy() {
        webView.destroy()
        super.onDestroy()
    }
}
