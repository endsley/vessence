"""BUILD_APK — rebuild or bump the Android APK.

These are build-system requests that always need the canonical bump script
(``startup_code/bump_android_version.py``). The proxy cascade has no fast
handler, so the class exists only to win the vector vote over RESTART_SERVER
/ DELEGATE_OPUS and hand a clear intent + protocol to Stage 3.

Tuned for Chieh's actual phrasings: "rebuild the APK", "bump the android
version", "make a new APK for me", etc. Generic "build" without the android
target falls to DELEGATE_OPUS so we don't grab unrelated build questions.
"""

CLASS_NAME = "BUILD_APK"
NEEDS_LLM = False

EXAMPLES = [
    # Rebuild — explicit APK target
    "rebuild the apk",
    "rebuild the apk for me",
    "can you rebuild the apk",
    "can you rebuild the apk for me",
    "please rebuild the apk",
    "rebuild the android apk",
    "rebuild jane's apk",
    "rebuild the android app",
    "rebuild the android build",
    "rebuild and redeploy the apk",
    # Build — explicit APK / android target
    "build the apk",
    "build a new apk",
    "build me a new apk",
    "build the android apk",
    "build the android app",
    "build a new android apk",
    "make a new apk",
    "make me a new apk",
    "build the new apk and deploy it",
    "build and deploy the apk",
    # Bump — Android version
    "bump the android version",
    "bump the apk version",
    "bump the android version and build",
    "bump the android version for me",
    "run the android version bump",
    "run the android bump script",
    "bump android and build",
    "bump android apk",
    # "deploy the apk"
    "deploy the new apk",
    "deploy the apk",
    "ship the new apk",
    "push a new apk",
    "cut a new apk",
    # Indirect imperatives
    "can you build a new android apk",
    "could you rebuild the apk",
    "i need a new apk",
    "i need you to rebuild the apk",
    "time to rebuild the apk",
    "let's rebuild the apk",
]

CONTEXT = None
