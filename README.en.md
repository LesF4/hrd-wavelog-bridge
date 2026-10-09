# HRD Logbook → Wavelog

[![Latest release](https://img.shields.io/github/v/release/LesF4/hrd-wavelog-bridge?label=version&color=2e7d32)](https://github.com/LesF4/hrd-wavelog-bridge/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/LesF4/hrd-wavelog-bridge/total?label=downloads&color=2e7d32)](https://github.com/LesF4/hrd-wavelog-bridge/releases)
[![MIT licence](https://img.shields.io/badge/licence-MIT-green)](LICENSE)

[🇫🇷 Français](README.md) · 🇬🇧 English

**Automatically sends every QSO logged in HRD Logbook (Ham Radio Deluxe) to your [Wavelog](https://www.wavelog.org).**
Keep logging in HRD as usual, by hand, from WSJT-X or from JS8Call: the contact shows up in your web log by itself.

Made by **F4MAJ / Jean-Bernard** for the [Les F4](https://github.com/LesF4) community.

![HRD Logbook → Wavelog: list of sent QSOs, HRD and Wavelog status lights](docs/img/app-en.png)

## At a glance

- **For whom?** Hams who keep their log in **HRD Logbook** and want it in their **Wavelog**, self-hosted or online.
- **All modes:** SSB, CW, FT8, JS8… whatever goes into HRD goes to Wavelog.
- **Hands off your log:** HRD itself sends each new QSO to the app (its *QSO Forwarding* feature). The app does not open your log file, unless you ask it to send your whole history.
- **Privacy-friendly:** only the QSO details go to Wavelog. Your contacts' address, e-mail and notes stay in HRD.
- **Nothing gets lost:** if the Internet is down, QSOs wait and are sent once it's back.
- **No duplicates:** Wavelog skips QSOs it already has.
- **Your history too:** one button sends your whole existing HRD log.
- **Bilingual** English / French, **free and open source** (MIT licence).

## Download

Go to [**Releases**](https://github.com/LesF4/hrd-wavelog-bridge/releases/latest) and get **`HRDtoWavelog-Setup-x.y.z.exe`**. It's a regular installer: Start menu, desktop icon, start with Windows, clean uninstall. No admin rights needed.

> **First start:** Windows may show "Windows protected your PC" because the app is not signed. Click **More info**, then **Run anyway**. The full source code is right here.

## Step-by-step setup

### 1. Install the app

Run `HRDtoWavelog-Setup-x.y.z.exe` and keep **Create a desktop shortcut** and **Start HRDtoWavelog with Windows** ticked.

### 2. Create an API key in Wavelog

In your web browser, log in to your Wavelog. Open **your account menu** (top right), then **API Keys**. Create a key with **Read & Write** rights and copy it.

### 3. Turn on QSO sending in HRD Logbook

In HRD Logbook, **Tools → Configure → QSO Forwarding**, **UDP send** section (*UDP Send*):
- enable sending QSOs over UDP;
- address **`127.0.0.1`** (or `localhost`), port **`12060`**;
- **OK**.

> This is what sends each new QSO to the app. It is separate from the UDP *receive* used by WSJT-X or JS8Call: both can be on at the same time.

### 4. Configure the app

On first start the **Settings** window opens:
- **UDP port**: `12060`, the same as in HRD.
- **Log file**: found automatically. It is only used by the *Send the whole HRD log…* button.
- **Address**: your Wavelog address, e.g. `https://wavelog.mysite.org`.
- **API key**: paste the key from step 2.
- Click **Test and load stations**, pick your **station**, then **Save**.

The app then asks whether to **also send the QSOs already in HRD**. Wavelog skips those it already has, so answering *Yes* creates no duplicates.

### 5. Check

**Both lights at the top of the window must be green.** Log a QSO in HRD: a few seconds later it shows up in the list ✔ and in your Wavelog.

> The app must be **running when you log the QSO**: HRD sends it only once. That's why starting with Windows is recommended. If QSOs were ever logged while the app was closed, the *Send the whole HRD log…* button catches up (Wavelog skips those it already has).

## Usage

| Status | Meaning |
|---|---|
| ✔ **Sent to Wavelog** | The QSO is in your Wavelog. |
| ✔ **Already in Wavelog** | Wavelog already had it, nothing was added. |
| ⏳ **Waiting** | Wavelog unreachable (Internet down…) or settings incomplete: it will be sent automatically. |
| ✖ **Rejected by Wavelog** | The reason is in the *Details* column. Fix the QSO in HRD if needed, then **Resend selection**. |

- **Send the whole HRD log…**: reads your HRD log file (read-only) and sends your entire history. QSOs already in Wavelog are skipped.
- The ✕ button hides the app next to the clock without stopping it. Right-click the icon → **Quit**.
- **Backup folder**: `qsos_envoyes_wavelog.adi` keeps an ADIF copy of everything sent.

## Troubleshooting

| Problem | Fix |
|---|---|
| **HRD light red** | The UDP port is already used by another program. Pick another port in *Settings* and set the same one in HRD (*QSO Forwarding*). |
| HRD light green but **no QSO arrives** | In HRD (*Tools → Configure → QSO Forwarding*), check that UDP **send** is on, to `127.0.0.1`, on the same port as the app. |
| *Send the whole HRD log…* can't find the log | In *Settings*, pick your `.hrdsql` file (usually `Documents\Ham Radio Deluxe\HRD Logbook\`). Only **Local/SQLite** logbooks are supported, the default in recent HRD versions. |
| **Wavelog light red** | Check your Internet connection and the Wavelog address. |
| "invalid API key" / "read-only" | Create a **Read & Write** key in Wavelog and paste it into *Settings*. |
| A QSO edited in HRD after it was sent | The app only sends **new** QSOs. Later corrections in HRD are not carried over: fix it in Wavelog too. |
| Antivirus blocks it | The app is unsigned and sends data over the Internet, which can worry some antivirus programs (Bitdefender in particular). Add an exception for `HRDtoWavelog.exe` and allow it in the antivirus firewall. |

Question, bug, idea? Open an [**issue**](https://github.com/LesF4/hrd-wavelog-bridge/issues).

## Where is my data?

In `%APPDATA%\HRDtoWavelog\`:
- `config.json`: your settings, including your API key, which stays on your PC only;
- `history.json`: the list shown in the window;
- `qsos_envoyes_wavelog.adi`: ADIF copy of the QSOs sent.

## Tested with

- HRD Logbook 6.9
- Self-hosted Wavelog
- Windows 11

## How it works (for the curious)

```
HRD Logbook ──(QSO Forwarding: UDP 12060, "contactinfo" XML)──▶ HRDtoWavelog ──(Wavelog API, HTTPS)──▶ Wavelog
```

The app only listens on the local machine (`127.0.0.1`), converts each received QSO to ADIF and sends it to Wavelog's `index.php/api/qso` API. Written in Python (tkinter UI). To run from source, run the tests or build the installer, see [`packaging/README.md`](packaging/README.md).

## See also

[**JS8Call → HRD Logbook**](https://github.com/LesF4/js8-hrd-bridge) sends your JS8Call QSOs into HRD. Together with this app, every JS8 QSO lands in HRD and then in Wavelog, hands-free.

## Licence

[MIT](LICENSE) © 2026 **F4MAJ / Jean-Bernard**. You may freely use, copy, modify and share this app, as long as you keep the copyright notice.

73 de F4MAJ!
