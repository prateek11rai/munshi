# Demo recording script (60–90 s, demo mode)

Everything on screen is made up (the demo projects tidepool and lantern). Nothing is recorded in demo mode.

## Before recording

1. Hide every other window (Option-click the desktop, or Hide Others) and pick a plain wallpaper. Close notification banners and turn on Do Not Disturb.
2. In the repo:

   ```sh
   uv run munshi demo load        # two made-up days, plus yesterday's journal page
   uv run munshi start --demo     # the buddy appears bottom-right
   ```

3. Drag the buddy where you want it (bottom-right reads well). Leave the card closed.
4. Optional, for the Refresh beat: warm the model once with `uv run munshi eval --demo --slots 1`, so Refresh answers in seconds instead of loading the model on camera.
5. Start the screen recording on the whole screen or a 1280 × 800 area around the buddy.

## The clicks

| Time | Do | Shows |
|---|---|---|
| 0:00–0:06 | Nothing. Let the buddy sit on the empty desktop. | The munshi with his ledger, always on top. |
| 0:06–0:12 | Click the buddy once. | The card opens beside him: **Where was I** with "updated 6 min ago" and the facts line from code. |
| 0:12–0:24 | Scroll slowly down the card. | **Today**: blocks newest first, with "away 50 min" gaps. **Yesterday**: three lines and "Active 6 h 45 min". |
| 0:24–0:32 | In **Hours**, click **Yesterday**, then **Today**. | The bars switch days; hours rounded to 15 min. |
| 0:32–0:38 | Click **Copy for timesheet**. | The button says "Copied". (Optional: paste into a TextEdit window you open just for this, then close it.) |
| 0:38–0:46 | Click **Pause**, then **30 min**. | Badge "Paused until …"; the buddy turns grey with a pause mark. |
| 0:46–0:50 | Click **Resume**. | Badge gone; the buddy is back in colour. |
| 0:50–0:58 | Click **Forget last hour**, then click it again to confirm. | The timeline now ends an hour earlier; the where note is rewritten by code. |
| 0:58–1:10 | Optional: click **Refresh now**. | "Writing…", then "Wrote N blocks." as the local model labels the last slots. |
| 1:10–1:20 | Click **Open journal**. In Finder, select yesterday's page and press Space (or Open With → Obsidian). | A plain Markdown page: summary, timeline, hours table. |
| 1:20–1:28 | Close Finder, click the card, press **Esc**. Drag the buddy a little. | The card hides; a drag moves him without opening the card. |

## After

- `Ctrl-C` in the terminal stops the app. `uv run munshi demo load` resets the demo (the Forget beat deleted an hour).
- Suggested captions, if any: "Click: where was I", "Hours, ready for a timesheet", "Pause and forget are one click", "A local model writes it; code checks every line".
