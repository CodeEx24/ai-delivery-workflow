# Mobile drivers (native apps)

For native mobile apps on a simulator or emulator. Tool names and flags change between
versions; the installed tool's help and schema are the authority. Stack-specific commands below
are **examples** — use what the project's `CLAUDE.md` and `docs/setup/` document.

## Contents

- [What the machine can run](#what-the-machine-can-run)
- [Picking a driver](#picking-a-driver)
- [Device lane and starting the device](#device-lane-and-starting-the-device)
- [Installing the right dev build](#installing-the-right-dev-build)
- [Starting the app and the local backend](#starting-the-app-and-the-local-backend)
- [The loop](#the-loop)
- [Android: adb](#android-adb)
- [iOS: simctl](#ios-simctl)
- [Maestro as the driver](#maestro-as-the-driver)
- [Logs and network](#logs-and-network)
- [Controls that resist automation](#controls-that-resist-automation)
- [Stopping everything](#stopping-everything)

## What the machine can run

| Host | Android emulator | iOS simulator |
|---|---|---|
| macOS | yes | yes (Xcode) |
| Windows / Linux | yes (Android SDK) | **no** |

A criterion that is iOS-only on a non-mac host is **BLOCKED** ("needs an iOS simulator — macOS
host or a cloud simulator service"), not a pass by analogy with Android. A physical device is a
human check; the approver escalates it.

Check what exists: `adb devices`, `emulator -list-avds` (Android); `xcrun simctl list devices`
(iOS). Missing SDK → say so and stop; do not install SDKs without the owner.

## Picking a driver

1. **A mobile-automation MCP** (tools for tap / type / swipe / screenshot / element tree on a
   simulator or emulator) — search deferred tools for `mobile`, `device`, `android`, `ios`,
   `simulator`. Best interaction loop when present.
2. **Maestro** (`maestro` CLI) — runs YAML flows against the app; the same flows become the
   committed E2E record. Drive it in small flows per step, or use its hierarchy/studio commands
   to find selectors.
3. **Platform CLIs** — `adb` (Android) and `xcrun simctl` (iOS) for screenshots, deep links,
   logs; `adb shell input` and `uiautomator dump` for basic interaction. Slow and coordinate-
   based, but always available with the SDK.
4. **Framework tooling** as a helper, e.g. the framework's dev menu / CLI to open the app on a
   device (Expo: `npx expo start --dev-client`, press `a` / `i`; React Native CLI: `run-android`).

Prefer selectors (test ids, accessibility labels) over coordinates. Coordinates break across
screen sizes and make a poor E2E flow.

## Device lane and starting the device

Hold the lane before booting anything (SKILL step 2). Then:

```bash
emulator -avd <name> -no-snapshot-save &   # Android; wait: adb wait-for-device + boot_completed
adb shell getprop sys.boot_completed       # "1" when ready
xcrun simctl boot "<device name or udid>"  # iOS; open -a Simulator to see it
xcrun simctl bootstatus <udid> -b          # waits until booted
```

Record the serial / udid you booted so step 8 shuts down exactly that one. If a device was
already booted by the user (not by another ticket), you may use it but do not shut it down.

## Installing the right dev build

Native dependencies are baked into the build; JavaScript or other hot-reloadable code is not.

1. Read `docs/setup/dev-builds.md`: which build id matches the current native-dependency set
   (often keyed by a fingerprint or the list of native modules) and how to fetch it (e.g.
   `eas build:list` / a download URL / building locally).
2. Compare with the branch: if the ticket added or changed a native dependency and the registry
   has no matching build, **stop: BLOCKED — needs a new dev build** (an owner action, not a builder fix).
   Do not "try the old build anyway": a missing native module crashes at start and wastes the run.
3. Install: `adb install -r <file>.apk` · `xcrun simctl install booted <App>.app` (unzip a
   `.tar.gz` / `.zip` first). Downloads go in the scratch folder; note them for cleanup.

## Starting the app and the local backend

- Backend first if needed: the commands and **port overrides** in `docs/setup/local-backend.md`,
  then its seed. The emulator reaches the host as `10.0.2.2` (Android emulator) or `localhost`
  (iOS simulator) — or use `adb reverse tcp:<port> tcp:<port>` so the app's `localhost` works on
  Android. Use whatever the recipe says.
- Start the bundler / dev server for this worktree on the documented port, in the background,
  and wait for its ready line. Then open the app on the device (dev client URL, deep link, or
  the framework's open command). Confirm the first screen shows before driving.
- Login codes come from the recipe's **local mail catcher** — open its web UI (a browser
  driver, or `curl` its API) to read the code. Never a real inbox.

## The loop

1. **Read the screen** — element tree (MCP tree, `maestro hierarchy`, `uiautomator dump`), not
   just pixels.
2. **Act** on one element.
3. **Wait** for the expected element/text (not a fixed sleep), then read the screen again.
4. **Screenshot** — every step, `<KEY>-<n>-AC<k>-step-<nn>.png` in `.delivery/jobs/<KEY>-<n>/round-<N>/screenshots/`.
5. Log the step: action → what the screen showed → file → the selector you used (you will reuse
   the selectors in the E2E flow).

## Android: adb

```bash
adb -s <serial> exec-out screencap -p > ".delivery/jobs/<KEY>-<n>/round-<N>/screenshots/<KEY>-<n>-AC1-step-01.png"
adb -s <serial> shell uiautomator dump /sdcard/ui.xml && adb -s <serial> exec-out cat /sdcard/ui.xml
adb -s <serial> shell input tap <x> <y>          # centre of the element's bounds from the dump
adb -s <serial> shell input text "hello%sworld"  # %s = space; no credentials on the command line you echo
adb -s <serial> shell input keyevent KEYCODE_BACK
adb -s <serial> shell am start -a android.intent.action.VIEW -d "<scheme>://path"   # deep link
adb -s <serial> shell svc wifi disable; adb -s <serial> shell svc data disable      # offline check
```

On Windows PowerShell, `>` redirection of binary output can corrupt PNGs; use Git Bash, or
`adb shell screencap -p /sdcard/s.png` then `adb pull /sdcard/s.png <path>`.

## iOS: simctl

```bash
xcrun simctl io booted screenshot ".delivery/jobs/<KEY>-<n>/round-<N>/screenshots/<KEY>-<n>-AC1-step-01.png"
xcrun simctl openurl booted "<scheme>://path"     # deep link
xcrun simctl launch booted <bundle id>
xcrun simctl terminate booted <bundle id>         # for the "restart the app" persistence check
xcrun simctl status_bar booted override --time 9:41   # optional: stable screenshots
```

`simctl` has no tap command: interact through a mobile MCP or Maestro.

## Maestro as the driver

```bash
maestro test .delivery/jobs/<KEY>-<n>/step.yaml   # a tiny flow for the next action(s)
maestro hierarchy                                  # element tree, to find ids/labels
maestro test --device <serial|udid> <flow>         # pick the device when several are booted
```

`takeScreenshot: <name>` inside a flow writes a PNG — use the step naming and point the output
at the working folder (check where your Maestro version writes it and move it if needed).
Scratch step flows live in the working folder; only the final consolidated flow goes into the
repo (see `e2e-and-reporting.md`). Pass the test account with `-e KEY=value` from the env, never
literal values in committed YAML.

## Logs and network

- Android: `adb logcat -c` before the run, then `adb logcat -d *:E` (errors) after each surface;
  filter by the app's tag/package (`--pid=$(adb shell pidof <package>)`).
- iOS: `xcrun simctl spawn booted log stream --level error --predicate 'process == "<App>"'`
  in the background during the run.
- The bundler / dev server output: red-box errors, warnings that indicate a real bug.
- Network: native apps rarely expose a request log to the agent. Use the **local backend's
  logs** (request paths and status codes) and any in-app network inspector the framework's dev
  tools provide. If nothing is readable, say "network not watched" — not "no errors".

## Controls that resist automation

System permission dialogs, native pickers (camera, photo library, date), biometric prompts,
OAuth sheets to a real provider, push-notification taps.

- Use the proper tool first: Maestro's permission handling (`launchApp: permissions: …`),
  `adb shell pm grant <package> <permission>`, `xcrun simctl privacy booted grant <service>
  <bundle id>`, simulator biometric enrolment, `xcrun simctl push` / `adb` broadcast for a test
  notification, `simctl addmedia` for photo fixtures.
- Still blocked → mark the criterion **BLOCKED** with the reason and the one manual step that
  would unblock it. Never reach the end state another way and call the UI criterion passed.

## Stopping everything

In step 8, stop what **you** started: the app (`am force-stop` / `simctl terminate`), the
bundler (its process / port), the local backend (the recipe's stop command with the ticket's
overrides), `adb reverse --remove-all` if you added reverses, re-enable wifi/data if you turned
them off, then shut down the emulator / simulator you booted (`adb -s <serial> emu kill`,
`xcrun simctl shutdown <udid>`). Leave a device the user booted running. Then release the lane.
