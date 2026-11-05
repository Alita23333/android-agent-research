package dev.alita.androidagent

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import dev.alita.androidagent.zcode.runtime.VisionConfig
import dev.alita.androidagent.zcode.runtime.ZCodeScreenFrames
import dev.alita.androidagent.zcode.runtime.ZCodeVisionConfigWriter
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(application = AgentApplication::class, sdk = [35])
class Phase9VisionBoundaryTest {
    private val context: Context = ApplicationProvider.getApplicationContext()
    @Test fun frameIdsAreUniqueBoundedAndSessionScoped() {
        val store = ZCodeScreenFrames(context)
        store.purge()
        val metadata = JSONObject().put("generation", 1).put("screenW", 1080)
        val first = store.save(byteArrayOf(1), metadata, "session-a").getString("shotId")
        val second = store.save(byteArrayOf(2), metadata, "session-a").getString("shotId")
        val third = store.save(byteArrayOf(3), metadata, "session-a").getString("shotId")
        assertNotEquals(first, second)
        assertNull(store.resolve(first, "session-a"))
        assertNotNull(store.resolve(second, "session-a"))
        assertNotNull(store.resolve(third, "session-a"))
        assertNull(store.resolve(third, "session-b"))
        assertNull(store.resolve("../../index", "session-a"))
        assertEquals(3, java.io.File(context.filesDir, "runtime/vision/shots").listFiles()!!.size)
        store.save(byteArrayOf(4), metadata, "session-b")
        assertNull(store.resolve(third, "session-a"))
        store.purge()
        assertEquals(0, java.io.File(context.filesDir, "runtime/vision/shots").listFiles()!!.size)
    }
    @Test fun oversizedOrUnownedFramesCannotBeStored() {
        val store = ZCodeScreenFrames(context)
        assertThrows(IllegalArgumentException::class.java) { store.save(ByteArray(153601), JSONObject(), "s") }
        assertThrows(IllegalArgumentException::class.java) { store.save(byteArrayOf(1), JSONObject(), "") }
    }
    @Test fun plaintextVisionEndpointsAreRefusedBeforeSaving() {
        assertThrows(IllegalArgumentException::class.java) {
            ZCodeVisionConfigWriter.saveFromUi(context, VisionConfig(true, "custom", "http://example.com/v1", "vlm"), "fixture")
        }
    }
    @Test fun captureCapabilityIsDeclaredAndRouteAResultHasNoPixelAttachment() {
        val bootstrap = context.assets.open("zcode-runtime/bootstrap.cjs").bufferedReader().use { it.readText() }
        assertTrue(bootstrap.contains("purgeVisionFrames();"))
        assertTrue(bootstrap.contains("/carrier/active"))
        assertTrue(bootstrap.contains("visionPipeline.executeSee"))
        val vision = context.assets.open("zcode-runtime/vision-pipeline.cjs").bufferedReader().use { it.readText() }
        assertTrue(vision.contains("beforeEgress: () => helpers.journal"))
        assertTrue(vision.contains("vision_stale_shot"))
        assertTrue(vision.contains("assertPublicEgressDestination"))
    }
}
