# Draft: feature request for OpenCode (to post on github.com/anomalyco/opencode)

Not posted. For the user to review and post from their own account.

---

**Title:** Desktop: support `opencode://new-session` deep links in the new layout

**Body:**

The desktop app supports `opencode://new-session?directory=<path>&prompt=<text>`, but only the
legacy layout acts on it. With **Settings → General → New layout** turned on, the link reaches the
app (the main log shows "deep link received via second-instance") and nothing happens.

Looking at desktop 1.19.6, the handler (`handleDeepLinks`) lives in `LegacyLayout`; `NewLayout`
has no equivalent, and there's no other outside way to open a new session in a given folder
(no "open project" command in the new layout, and the new-session shortcut reuses the current
tab's folder).

**Use case:** I'm building a push-to-talk voice tool. Saying "Assistant, <request>" should open
a new, visible OpenCode session in a chosen folder with the request filled in. The deep link
is exactly the right interface, and it works today with the old layout, which the settings say
is only available for a limited time.

**Request:** handle `opencode://new-session` (and `open-project`) in the new layout, ideally
with an option to send the prompt immediately (for example `&submit=1`).

**Steps to reproduce:**
1. Turn on Settings → General → New layout.
2. Run `xdg-open "opencode://new-session?directory=/tmp/test&prompt=hello"` (Linux).
3. The app comes to the front, but no session opens for `/tmp/test` and the prompt isn't filled in.
   (The legacy layout's code handles this link; I haven't confirmed it live with New layout off.)

Environment: OpenCode desktop 1.19.6, Linux Mint (X11).
