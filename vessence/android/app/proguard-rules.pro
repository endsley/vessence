# Retrofit + Gson
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.google.gson.** { *; }
-keep class * extends com.google.gson.TypeAdapter
-keep class * implements com.google.gson.TypeAdapterFactory
-keep class * implements com.google.gson.JsonSerializer
-keep class * implements com.google.gson.JsonDeserializer
-keepclassmembers,allowobfuscation class * {
    @com.google.gson.annotations.SerializedName <fields>;
}
-dontwarn retrofit2.**
-keep class retrofit2.** { *; }
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}

# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Vosk speech recognition
-keep class org.vosk.** { *; }

# Google Credential Manager / Sign-In
-keep class com.google.android.libraries.identity.** { *; }
-keep class androidx.credentials.** { *; }

# Media3 / ExoPlayer
-keep class androidx.media3.** { *; }
-dontwarn androidx.media3.**

# Keep data classes used with Gson (adjust package to match your models)
-keep class com.vessences.android.data.** { *; }
-keep class com.vessences.android.model.** { *; }
-keep class com.vessences.android.api.** { *; }
-keep class com.vessences.android.util.ChatPersistence$* { *; }
