# Vessences Android

- `https://vault.vessences.com/`

Why this shape:

- it preserves the exact current Vault behavior instead of rebuilding a parallel mobile client
- file upload, camera attach, and future web improvements stay aligned automatically
- login stays focused on authorization instead of showing app navigation before the user is signed in

Notes:

- the app opens the Vault root and lets the server decide whether to show the login screen or the authenticated app
- login is Google OAuth only
- file/camera upload is handled via Android's chooser and passed through to the existing web upload flow
