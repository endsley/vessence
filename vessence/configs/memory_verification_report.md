# Memory Verification Report — 2026-07-07 03:02

Checked: 20 | Stale: 15 | Fixed: 14 | Deleted: 0 | Errors: 0 | Skipped recent: 251

- **UPDATED** `b6d11def-67d` — Actual git history confirms the hashes are in /home/chieh/code/waterlily, not Vessence. Current code/search confirms the HTML and backend-module claims, but Codex's 422-pass/1-failure caveat is now wrong because a fresh pytest run passed 423 tests.
- **KEPT** `4bdf3b6f-873` — Codex was wrong to treat the memory as stale. I confirmed the code has no Vessence references to MusiBaby/Bluetooth troubleshooting, but live bluetoothctl on endsley verifies Controller 00:02:72:BF:D0:D4 and device MusiBaby-M68.
- **UPDATED** `4bbfdbb8-95c` — Codex was right that the original memory is truncated and there is no Vessence repo/cron automation, but wrong that live bluetoothctl/rfkill state could not be verified here; current host checks confirm powered, unblocked, connected, and active services.
- **UPDATED** `5b0670e6-0e8` — Code and cache confirm Codex's verifiable claims; the existing memory is truncated after the Madeleine claim and should qualify the manual totals as pasted external data.
- **UPDATED** `0b0896df-9a4` — Codex was right: the stored memory is truncated and omits the separate legacy v1 MCP reader; confirmed against the actual spec, loader, v1 router, and v2 classifier files.
- **UPDATED** `6d032384-520` — Current code confirms the main TTS claims, but the stored memory is truncated and omits the VoiceController non-sentence path and ArticleReaderV2Activity owner.
- **UPDATED** `8ff0667e-46c` — Codex was right on the routing and Android paths after checking jane_web/main.py, jane_web/pipeline_selection.py, the Android files, env file, service file, live process env, and logs; the stored memory is truncated and dated, so it should be updated.
- **UPDATED** `81ce9c38-874` — Confirmed in the actual code. The old memory is truncated and misses that create_music_playlist_from_query is now a facade over music_playlists.music_playlist_from_query, plus the Gemma naming is historical while the local LLM default is qwen2.5:7b.
- **UPDATED** `8c7cda38-d7f` — Codex was right: the code and env values match, but the existing memory is truncated at the end and should be repaired.
- **UPDATED** `ce56ca65-8a9` — Actual code confirms the files and class metadata, but the old memory's final import wording is truncated/wrong; stage1_classifier imports from intent_classifier.v2.classifier, not intent_class.
- **UPDATED** `2dc3dec8-82f` — Codex was substantively right, but the stored memory is truncated and should be rewritten. I verified the routing, env flag helpers, endpoint imports, Stage 1 classifier behavior, and model defaults against the actual code.
- **UPDATED** `909d51ad-8ee` — Actual code confirms Codex's partial verdict: artifacts and route still exist, but alias glob mapping and newest-mtime resolution now live in `jane_web/release_downloads.py`, not directly in `jane_web/main.py`.
- **UPDATED** `6baa82c6-fb9` — Stale/truncated memory. Codex was mostly right about the fast-send path and current files, but it missed the important current-code caveat that params metadata always carries a confidence key, so v3 params without numeric confidence do not direct-send.
- **UPDATED** `c9e822b9-0c7` — Confirmed in current code: Gradle reads root version.json, the bump script builds/verifies/deploys as described, and main.py now delegates Android version fallback to ReleaseDownloads instead of literal fallback fields.
- **UPDATED** `44aab1b0-7fe` — Confirmed from the current code: the model constants are still correct, but the memory needed clearer v2/v3 routing and gate wording.
