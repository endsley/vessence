---
Title: "Integrate Mozilla's Readability.js into Android ArticleReaderV2Activity"
Priority: 2
Status: completed
Created: 2026-04-18
---

## 1. Problem
The current "Summarize Now v2 (WebView)" feature in the Android app uses a basic text extraction method that fails to remove all ads and clutter from articles. The user has requested a more robust solution. Additionally, the `preview` TextView for the extracted text is not scrollable.

## 2. Goal
Replace the existing text extraction logic with Mozilla's `Readability.js` to provide a much cleaner, "reader mode" output. Also, fix the scrolling issue.

## 3. Work Completed
- The `Readability.js` library has already been fetched and saved to `/home/chieh/ambient/vessence/android/app/src/main/assets/Readability.js`.
- `ArticleReaderV2Activity.kt` now injects `Readability.js` into the WebView and extracts `textContent` from `new Readability(document).parse()`.
- The preview `TextView` is scrollable via `ScrollingMovementMethod()`.
- `cleanArticleText()` now only normalizes whitespace/newlines and caps article length, leaving clutter removal to Readability.
- Verified with `./gradlew :app:compileDebugKotlin`.

## 4. Proposed Code Changes
The file `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/ArticleReaderV2Activity.kt` needs to be modified as follows:

1.  **Update `articleExtractionJs()`:** Replace the current simple script with a call to `new Readability(document).parse()`.
2.  **Update `extractAndSpeak()`:** Add logic to read the `Readability.js` asset from the file system, inject it into the WebView before evaluation, and correctly parse the `textContent` from the JSON object that `Readability.js` returns. A new helper function, `readAsset()`, should be added.
3.  **Simplify `cleanArticleText()`:** Since `Readability.js` provides much cleaner output, the existing keyword-based filtering should be removed and the function simplified to just handle whitespace and newlines.
4.  **Fix Scrolling:** In the `onCreate` method, modify the `preview` TextView's definition to include `movementMethod = ScrollingMovementMethod()` to make it scrollable.

## 5. Blocker / Context for Next Session
My repeated attempts to automate these file modifications using a temporary Python script (`run_shell_command` with `write_file`) have failed due to complex, recurring Python `SyntaxError`s related to string literals, quoting, and indentation when trying to generate the new Kotlin code within the script.

The next agent should be aware of this and may need to perform the code modifications manually using the `replace` tool, or by constructing a more robust script that can handle the complex string generation without syntax errors. The "overwrite entire file" approach is sound, but the script generation has been the point of failure.
