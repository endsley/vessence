package com.vessences.android.voice

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import java.nio.FloatBuffer

/**
 * Lightweight wake word detector using OpenWakeWord ONNX models.
 * Pipeline: raw PCM → mel spectrogram → audio embeddings → wake word classifier.
 *
 * Uses ~4% of a single ARM core — designed for always-on background listening.
 */
class OpenWakeWordDetector(
    context: Context,
    private val wakeWordModelName: String = "hey_jane.onnx",
    private val threshold: Float = 0.5f,
) : AutoCloseable {

    companion object {
        const val SAMPLE_RATE = 16_000
        const val CHUNK_SIZE = 1280  // 80ms at 16kHz
        private const val MEL_BINS = 32
        private const val EMBEDDING_DIM = 96
        private const val FEATURE_WINDOW = 16  // embeddings for classifier
        private const val MEL_WINDOW = 76       // mel frames needed for one embedding
        private const val MEL_STEP = 8          // stride between embedding windows
        private const val MAX_MEL_FRAMES = 300  // ~24s of mel history
    }

    private val env = OrtEnvironment.getEnvironment()
    private val melSession: OrtSession
    private val embeddingSession: OrtSession
    private val classifierSession: OrtSession

    // Raw audio context buffer — keeps last 480 samples for mel overlap
    private val rawContext = FloatArray(480)
    private var hasContext = false

    // Persistent mel-frame buffer — accumulates across feedAudio() calls
    private val melBuffer = ArrayDeque<FloatArray>()  // each entry is MEL_BINS floats
    private var melFramesProcessed = 0  // how many mel frames have been consumed by embeddings

    private val embeddingBuffer = ArrayDeque<FloatArray>()  // each is 96-dim

    init {
        val opts = OrtSession.SessionOptions().apply {
            setIntraOpNumThreads(1)
        }
        melSession = env.createSession(
            context.assets.open("openwakeword/melspectrogram.onnx").use { it.readBytes() }, opts
        )
        embeddingSession = env.createSession(
            context.assets.open("openwakeword/embedding_model.onnx").use { it.readBytes() }, opts
        )
        classifierSession = env.createSession(
            context.assets.open("openwakeword/$wakeWordModelName").use { it.readBytes() }, opts
        )

        // Log model info for debugging
        android.util.Log.i("OWWDetector", "Models loaded: mel=${melSession.inputNames}, " +
                "embed=${embeddingSession.inputNames}, classify=${classifierSession.inputNames}")

        // Warmup: feed 4 seconds of silence to fill buffers
        val warmup = FloatArray(SAMPLE_RATE * 4)
        for (i in warmup.indices step CHUNK_SIZE) {
            val end = minOf(i + CHUNK_SIZE, warmup.size)
            feedAudio(warmup.copyOfRange(i, end))
        }
    }

    /**
     * Feed a chunk of audio (float[], normalized to [-1, 1]) and return the
     * wake word detection score (0.0 to 1.0).
     */
    fun feedAudio(chunk: FloatArray): Float {
        // Step 1: Compute mel spectrogram for this chunk (uses rawContext for overlap)
        val melFrames = computeMel(chunk)

        // Update raw context — keep last 480 samples for next mel computation
        if (chunk.size >= 480) {
            System.arraycopy(chunk, chunk.size - 480, rawContext, 0, 480)
        } else {
            // Shift existing context and append new samples
            val shift = 480 - chunk.size
            System.arraycopy(rawContext, chunk.size, rawContext, 0, shift)
            System.arraycopy(chunk, 0, rawContext, shift, chunk.size)
        }
        hasContext = true

        if (melFrames == null) return 0f

        // Step 2: Accumulate mel frames in persistent buffer
        val numFrames = melFrames.size / MEL_BINS
        for (f in 0 until numFrames) {
            val frame = FloatArray(MEL_BINS)
            System.arraycopy(melFrames, f * MEL_BINS, frame, 0, MEL_BINS)
            melBuffer.addLast(frame)
        }

        // Cap mel buffer to prevent unbounded growth
        while (melBuffer.size > MAX_MEL_FRAMES) {
            melBuffer.removeFirst()
            // Adjust processed count since we removed frames from the front
            if (melFramesProcessed > 0) melFramesProcessed--
        }

        // Step 3: Extract embeddings from accumulated mel frames
        // We can compute a new embedding every MEL_STEP frames
        while (melBuffer.size - melFramesProcessed >= MEL_WINDOW) {
            val embedding = computeSingleEmbedding(melFramesProcessed)
            if (embedding != null) {
                embeddingBuffer.addLast(embedding)
            }
            melFramesProcessed += MEL_STEP
        }

        // Keep only last 120 embeddings (~10s)
        while (embeddingBuffer.size > 120) {
            embeddingBuffer.removeFirst()
        }

        // Need at least FEATURE_WINDOW embeddings for classification
        if (embeddingBuffer.size < FEATURE_WINDOW) return 0f

        // Step 4: Classify using last FEATURE_WINDOW embeddings
        return classify()
    }

    /**
     * Feed raw PCM shorts (from AudioRecord) and return whether the wake word
     * was detected (score >= threshold).
     */
    private var logCounter = 0
    var lastScore: Float = 0f
        private set

    fun feedShorts(buffer: ShortArray, length: Int): Boolean {
        if (length <= 0) return false  // AudioRecord.read() can return error codes
        val floats = FloatArray(length)
        for (i in 0 until length) {
            floats[i] = buffer[i] / 32768f
        }
        val score = feedAudio(floats)
        lastScore = score
        logCounter++
        if (score > 0.05f || logCounter % 62 == 0) {
            android.util.Log.d("OWWDetector",
                "score=%.4f thr=%.2f mel=%d emb=%d".format(
                    score, threshold, melBuffer.size, embeddingBuffer.size))
        }
        return score >= threshold
    }

    fun isDetected(score: Float): Boolean = score >= threshold

    /**
     * Soft reset: clears classifier/embedding state but keeps mel buffer warm
     * so detection isn't dead for several seconds after wake word trigger.
     */
    fun reset() {
        embeddingBuffer.clear()
        // Keep mel buffer and raw context — avoids cold-start delay
        // Just reset the embedding extraction position to re-process recent mel frames
        melFramesProcessed = maxOf(0, melBuffer.size - MEL_WINDOW)
    }

    /**
     * Compute mel spectrogram for a single audio chunk.
     * Uses rawContext (480 samples) + chunk for proper overlap.
     */
    private fun computeMel(chunk: FloatArray): FloatArray? {
        val contextSize = 480
        val totalSize = contextSize + chunk.size

        // Build input: context + new chunk
        val input = FloatArray(totalSize)
        if (hasContext) {
            System.arraycopy(rawContext, 0, input, 0, contextSize)
        }
        // else: zeros for context on first call (fine for warmup)
        System.arraycopy(chunk, 0, input, contextSize, chunk.size)

        val inputTensor = OnnxTensor.createTensor(
            env, FloatBuffer.wrap(input), longArrayOf(1, input.size.toLong())
        )

        try {
            val result = melSession.run(mapOf("input" to inputTensor))
            try {
                val outputTensor = result[0].value
                return when (outputTensor) {
                    is Array<*> -> {
                        // Shape: [1, 1, N_FRAMES, 32]
                        @Suppress("UNCHECKED_CAST")
                        val arr = outputTensor as Array<Array<Array<FloatArray>>>
                        val frames = arr[0][0]
                        FloatArray(frames.size * MEL_BINS) { i ->
                            val frame = i / MEL_BINS
                            val bin = i % MEL_BINS
                            // Standard OpenWakeWord normalization
                            frames[frame][bin] / 10f + 2f
                        }
                    }
                    else -> null
                }
            } finally {
                result.close()
            }
        } finally {
            inputTensor.close()
        }
    }

    /**
     * Compute a single embedding from MEL_WINDOW consecutive mel frames
     * starting at the given offset in melBuffer.
     */
    private fun computeSingleEmbedding(startFrame: Int): FloatArray? {
        if (startFrame + MEL_WINDOW > melBuffer.size) return null

        val window = FloatArray(MEL_WINDOW * MEL_BINS)
        for (f in 0 until MEL_WINDOW) {
            val frame = melBuffer[startFrame + f]
            System.arraycopy(frame, 0, window, f * MEL_BINS, MEL_BINS)
        }

        val inputTensor = OnnxTensor.createTensor(
            env, FloatBuffer.wrap(window),
            longArrayOf(1, MEL_WINDOW.toLong(), MEL_BINS.toLong(), 1)
        )

        try {
            val result = embeddingSession.run(mapOf("input_1" to inputTensor))
            try {
                val output = result[0].value
                return when (output) {
                    is Array<*> -> {
                        @Suppress("UNCHECKED_CAST")
                        val arr = output as Array<Array<Array<FloatArray>>>
                        arr[0][0][0].copyOf()  // [1, 1, 1, 96] -> [96]
                    }
                    else -> FloatArray(EMBEDDING_DIM)
                }
            } finally {
                result.close()
            }
        } finally {
            inputTensor.close()
        }
    }

    private fun classify(): Float {
        val startIdx = embeddingBuffer.size - FEATURE_WINDOW
        val input = FloatArray(FEATURE_WINDOW * EMBEDDING_DIM)
        for (f in 0 until FEATURE_WINDOW) {
            val emb = embeddingBuffer[startIdx + f]
            System.arraycopy(emb, 0, input, f * EMBEDDING_DIM, EMBEDDING_DIM)
        }

        val inputTensor = OnnxTensor.createTensor(
            env, FloatBuffer.wrap(input),
            longArrayOf(1, FEATURE_WINDOW.toLong(), EMBEDDING_DIM.toLong())
        )

        try {
            val result = classifierSession.run(mapOf(classifierSession.inputNames.first() to inputTensor))
            try {
                val output = result[0].value
                return when (output) {
                    is Array<*> -> {
                        @Suppress("UNCHECKED_CAST")
                        (output as Array<FloatArray>)[0][0]
                    }
                    else -> 0f
                }
            } finally {
                result.close()
            }
        } finally {
            inputTensor.close()
        }
    }

    override fun close() {
        classifierSession.close()
        embeddingSession.close()
        melSession.close()
    }
}
