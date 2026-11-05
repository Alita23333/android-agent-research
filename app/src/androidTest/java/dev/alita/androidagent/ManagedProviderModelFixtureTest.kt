package dev.alita.androidagent

import android.os.Build
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Product-store fixture import only. Actual admission must use the production UI separately. */
@RunWith(AndroidJUnit4::class)
class ManagedProviderModelFixtureTest {
    @Test fun importOnly() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val args = InstrumentationRegistry.getArguments()
        require(context.packageName == "dev.alita.androidagent")
        TestDeviceTarget.require(InstrumentationRegistry.getArguments().getString("deviceTarget"))
        val id = requireNotNull(args.getString("fixtureId"))
        require(id.matches(Regex("aa_model_[0-9]{10,22}")))
        val version = requireNotNull(args.getString("revision"))
        require(version in setOf("v1", "v2"))
        val graph = (context.applicationContext as AgentApplication).graph
        assertFalse(graph.providerAdmission.hostActive())
        val reviewFile = File(context.filesDir, "provider-reviews.json")
        val before = if (reviewFile.exists()) reviewFile.readBytes() else null
        val description = "Compute SHA256 and byte count for explicit base64 data. WAIT input delays30seconds. No file or network access."
        val script = """
            const rl=require('node:readline'),crypto=require('node:crypto');
            rl.createInterface({input:process.stdin}).on('line',line=>{
              const r=JSON.parse(line);const reply=result=>process.stdout.write(JSON.stringify({jsonrpc:'2.0',id:r.id,result})+'\n');
              if(r.method==='initialize')return reply({protocolVersion:'1.0',tools:[{name:'compute',version:'1',description:${JSONObject.quote(description)},inputSchema:{type:'object',required:['base64'],additionalProperties:false,properties:{base64:{type:'string',maxLength:21848}}},capabilities:['data-transform'],sideEffect:'NONE',supportsCancellation:true}]});
              if(r.method!=='tools/call'||r.params.name!=='compute')throw Error('unsupported request');
              const b=Buffer.from(r.params.arguments.base64,'base64');
              const finish=()=>reply({ok:true,data:{version:'$version',bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex'),uid:process.getuid(),pid:process.pid}});
              if(b.toString().startsWith('WAIT:'))setTimeout(finish,30000);else finish();
            });
        """.trimIndent()
        val manifest = JSONObject().put("id", id).put("version", version)
            .put("command", JSONArray(listOf("${'$'}{APK_NODE}", "${'$'}{DIR}/provider.cjs")))
        val bytes = ByteArrayOutputStream()
        ZipOutputStream(bytes).use { zip ->
            listOf("provider.json" to manifest.toString(), "provider.cjs" to script).forEach { (name, body) ->
                zip.putNextEntry(ZipEntry(name)); zip.write(body.toByteArray()); zip.closeEntry()
            }
        }
        val item = graph.providers.install(bytes.toByteArray().inputStream())
        assertTrue(if (before == null) !reviewFile.exists() else before.contentEquals(reviewFile.readBytes()))
        assertNull(graph.registry.find("$id.compute"))
        File(context.cacheDir, "$id-$version.json").writeText(JSONObject().put("id", id)
            .put("version", version).put("contentHash", item.directory.name).put("description", description)
            .put("directory", item.directory.canonicalPath).put("admissionUnchanged", true)
            .put("registryAbsent", true).put("script", script).toString(2))
    }
}
