# Job #57: Android Chat — Image Thumbnails + Fullscreen Viewer

Priority: 2
Status: completed
Created: 2026-03-30

## Description
When Jane's response references an image (vault path or URL), show a clickable thumbnail in the chat bubble. Tapping opens the image fullscreen.

### Changes
- Parse Jane's response for image references (vault paths, URLs)
- Render a small thumbnail inline in the chat message
- Tap thumbnail → fullscreen image viewer overlay
- Support both vault-hosted images and external URLs
