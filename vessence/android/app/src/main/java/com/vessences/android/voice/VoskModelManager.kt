package com.vessences.android.voice

import android.content.Context
import com.vessences.android.data.api.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.Request
import org.vosk.Model
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream

class VoskModelManager(
    private val context: Context,
) {
    private val lock = Mutex()
    private var model: Model? = null

    /**
     * Returns the cached model if already loaded, or null.
     * Does NOT download — use [ensureModel] for that.
     * Safe to call from any thread.
     */
    fun getModelSync(): Model? {
        model?.let { return it }
        // Try to load from disk if already downloaded
        val modelDir = File(File(context.filesDir, "vosk"), MODEL_DIR_NAME)
        if (looksReady(modelDir)) {
            return try {
                Model(modelDir.absolutePath).also { model = it }
            } catch (_: Exception) {
                null
            }
        }
        return null
    }

    suspend fun ensureModel(onStatus: (String) -> Unit): Model = lock.withLock {
        model?.let { return it }

        val modelDir = withContext(Dispatchers.IO) {
            onStatus("Preparing offline voice model")
            ensureModelDirectory(onStatus)
        }

        return Model(modelDir.absolutePath).also { model = it }
    }

    private fun ensureModelDirectory(onStatus: (String) -> Unit): File {
        val baseDir = File(context.filesDir, "vosk")
        val modelDir = File(baseDir, MODEL_DIR_NAME)
        if (looksReady(modelDir)) return modelDir

        baseDir.mkdirs()
        val zipFile = File(context.cacheDir, "$MODEL_DIR_NAME.zip")
        onStatus("Downloading offline voice model")
        val request = Request.Builder().url(MODEL_ZIP_URL).build()
        ApiClient.getOkHttpClient().newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw IllegalStateException("Voice model download failed: HTTP ${response.code}")
            }
            val body = response.body ?: throw IllegalStateException("Voice model download was empty")
            FileOutputStream(zipFile).use { output -> body.byteStream().copyTo(output) }
        }

        onStatus("Installing offline voice model")
        unzip(zipFile, baseDir)
        zipFile.delete()

        if (!looksReady(modelDir)) {
            val extracted = baseDir.listFiles()?.firstOrNull { looksReady(it) }
            if (extracted != null && extracted.name != MODEL_DIR_NAME) {
                extracted.copyRecursively(modelDir, overwrite = true)
            }
        }

        if (!looksReady(modelDir)) {
            throw IllegalStateException("Offline voice model is missing required files")
        }
        return modelDir
    }

    private fun unzip(zipFile: File, destination: File) {
        ZipInputStream(zipFile.inputStream().buffered()).use { zip ->
            var entry = zip.nextEntry
            while (entry != null) {
                val outFile = File(destination, entry.name)
                if (entry.isDirectory) {
                    outFile.mkdirs()
                } else {
                    outFile.parentFile?.mkdirs()
                    FileOutputStream(outFile).use { output -> zip.copyTo(output) }
                }
                zip.closeEntry()
                entry = zip.nextEntry
            }
        }
    }

    private fun looksReady(dir: File): Boolean =
        dir.isDirectory &&
            File(dir, "am").isDirectory &&
            File(dir, "conf").isDirectory &&
            File(dir, "ivector").isDirectory

    companion object {
        private const val MODEL_DIR_NAME = "vosk-model-small-en-us-0.15"
        private const val MODEL_ZIP_URL =
            "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    }
}
