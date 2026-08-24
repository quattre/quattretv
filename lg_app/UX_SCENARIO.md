# QuattreTV — UX Scenario

**App name:** QuattreTV
**App ID:** com.quattre.tv
**Version:** 1.1.0
**Vendor:** Quattre Internet SL
**Category:** Video / Entertainment
**Languages:** Spanish (es-ES)
**Input:** LG Magic Remote and standard TV remote. Pointer is not required —
every screen is fully operable with the 4-way pad, OK and BACK.

---

## 1. What the app does

QuattreTV is the television client for QuattreTV, a subscription IPTV service
operated by Quattre Internet SL for its own customers in Spain. The app lets a
subscriber watch the live TV channels, the video-on-demand catalogue and their
own recordings included in their subscription.

The service is **subscription-only**. There is no free tier and no public
content: every screen beyond the sign-in screen requires valid customer
credentials. A test account for the review team is provided in section 2.

All content is delivered by Quattre Internet SL under its own distribution
agreements. There is no user-generated content, no advertising, no in-app
purchase and no external link out of the app.

---

## 2. Test account for the review team

| | |
|---|---|
| **User** | `lgreview` |
| **Password** | `QuattreLG2026` |
| **Subscription** | Full package — all live channels, VOD and recordings |
| **Expiry** | None. The account does not expire. |
| **Concurrent devices** | 5 |
| **Parental PIN** | `1234` (see section 6) |
| **Locked channel to test the PIN with** | **Dark**, channel number 29 |

The account is ready before submission and stays active for the whole review.
Sign-in is described in section 4.2.

---

## 3. Requirements to run the app

- The TV must be connected to the internet.
- No other hardware, no companion app and no pairing step is needed.
- All network traffic is HTTPS.

If the TV has no network when the app starts, the app does **not** show a blank
screen: see section 7.

---

## 4. Screen by screen

### 4.1 Splash / connection screen

The first screen shows the QuattreTV logo and the text *Conectando…*
("Connecting…"). The app asks the service whether it is reachable before loading
anything else.

- **Success:** the portal loads. Typically under one second.
- **Failure:** see section 7 (error handling). A *Reintentar* ("Retry") button
  receives the focus so OK on the remote retries immediately, and the app also
  retries by itself.

No key press is required. There is no fixed timer that navigates blindly.

### 4.2 Sign-in screen

Shown only the first time the app runs on a TV, or after the customer's device
has been removed from their account.

| Field | Behaviour |
|---|---|
| **Usuario** (user) | Text field. Focus opens the webOS on-screen keyboard. |
| **Contrasena** (password) | Masked field. Focus opens the on-screen keyboard. |
| **Entrar** (sign in) | Button. |

**Remote control:**

| Key | Action |
|---|---|
| ▲ / ▼ | Move between user, password and the sign-in button |
| OK | Open the keyboard on a field, or sign in when on the button |
| BACK | Close the on-screen keyboard |

Once signed in, the TV is registered against the customer's account and the app
goes straight to the channel list on every later start. The credentials are not
asked again.

If the credentials are wrong, or the account has no subscription, or the device
limit for the account is already used, the screen shows the reason in plain
Spanish and stays on the sign-in screen. It never leaves the user on a dead end.

### 4.3 Channel list (home screen)

The main screen. A list of channels on the left, each with its number, name,
logo and the programme currently on air. The channel under the cursor plays in a
preview window on the right.

| Key | Action |
|---|---|
| ▲ / ▼ | Move up and down the channel list |
| **0–9** | Type a channel number to jump straight to it |
| **OK** | Play the selected channel full screen |
| **►** | Open the programme guide for the selected channel |
| **◄** | Open the main menu |
| **BACK** | Same as ◄ — open the main menu |

Channels marked with 🔒 are adult channels. See section 6.

### 4.4 Full-screen playback

| Key | Action |
|---|---|
| ▲ / ▼ (or CH+ / CH−) | Previous / next channel |
| **►** | Show the channel banner again without changing channel |
| **OK** or **BACK** | Leave full screen and go back to the channel list |
| Volume | Handled by the TV itself |

Changing channel shows a banner for a few seconds with the channel number, name,
the programme on air and what is on next.

### 4.5 Main menu

Opened with ◄ or BACK from the channel list. A vertical list:

- **Canales** — the channel list
- **Categorias** — filter channels by genre
- **Solo favoritos** — show only the channels the customer marked as favourite
- **Peliculas** — film catalogue
- **Series** — series catalogue
- **Mis grabaciones** — the customer's own recordings

The menu is built from what the customer's subscription actually includes: an
option that does not apply to the account is not shown at all, never shown
disabled or leading to an empty screen.

| Key | Action |
|---|---|
| ▲ / ▼ | Move through the options |
| **OK** | Enter the option |
| **◄** / **BACK** | Back to the channel list |

### 4.6 Programme guide

Opened with ► from the channel list. Lists the programmes of the selected
channel with start time, end time and description.

| Key | Action |
|---|---|
| ▲ / ▼ | Move through the programmes |
| **OK** | Play the programme (past programmes play from the archive) |
| **◄** / **BACK** | Back to the channel list |

### 4.7 Films and series

| Key | Action |
|---|---|
| ▲ / ▼ | Move through the catalogue |
| **OK** | Play the film, or open the episode list of a series |
| **◄** / **BACK** | Back to the main menu (from the episode list, back to the series list) |

### 4.8 Recordings

The customer's own recordings, with their state (recording, ready, failed).

| Key | Action |
|---|---|
| ▲ / ▼ | Move through the list |
| **OK** | Play a finished recording |
| **►** | Delete the selected recording (asks for confirmation) |
| **◄** / **BACK** | Back to the channel list |

---

## 5. Complete remote control map

| Key | Where | Action |
|---|---|---|
| ▲ ▼ | everywhere | Move / change channel |
| ◄ | channel list | Open the main menu |
| ◄ | any other screen | Back to the previous screen |
| ► | channel list | Programme guide |
| ► | full screen | Show the channel banner |
| OK | everywhere | Enter / play |
| BACK | everywhere | Back to the previous screen; from the channel list, the main menu |
| 0–9 | channel list | Jump to channel number |
| 0–9 | PIN screen | Enter the PIN |

**Back behaviour.** `disableBackHistoryAPI` is `true` in `appinfo.json`, so the
app handles BACK itself. There is no screen the user can get stuck in: BACK
always leads back towards the channel list, and BACK on the channel list opens
the main menu. Leaving the app is done with the HOME key of the remote, handled
by webOS.

---

## 6. Parental control and adult content — **please read**

**The service carries adult channels.** They are declared here on purpose.

They are handled as follows:

1. Adult channels appear in the list marked with a padlock (🔒) and their name.
   Nothing else about them is shown.
2. **The stream address of a locked channel is never sent to the TV.** The
   server withholds it. The app physically cannot play the channel, with or
   without the app's cooperation — the PIN is not a screen the app draws over
   the video, it is the server refusing to hand over the content.
3. The preview window does not play a locked channel either. It shows
   *"Canal bloqueado — pulsa OK e introduce el PIN"* ("Channel locked — press OK
   and enter the PIN").
4. Pressing OK on a locked channel opens the PIN screen. The PIN is entered with
   the number keys. ◄ or BACK cancels.
5. A correct PIN unlocks the device for **30 minutes**, after which it locks
   again by itself. A wrong PIN is rate-limited.
6. The same check is applied to films, series and episodes rated for adults.
7. The PIN is set by the account holder and can be changed from the customer's
   web account. It is not stored on the TV.

**How to verify it during the review.** Channel **29, "Dark"**, is an adult
channel; the test account's PIN is **1234**. The behaviour can be checked in both
directions:

1. On the channel list, channel 29 shows a padlock. The preview window does not
   play it and says the channel is locked.
2. Press OK on it: the PIN screen appears. Enter a wrong PIN and it is rejected.
3. Enter `1234` and the channel plays.
4. Channel **30, "Dark Sin X"**, is the same channel without the adult content
   and is *not* locked, which shows the lock applies per channel and not to the
   whole list.

What happens underneath, and it is the part worth checking: when the channel is
locked the server sends the channel entry **with an empty address**. There is no
stream URL on the television to be found. Verified against the live service —
requesting the address of channel 29 without the PIN returns an error, not a
URL.

---

## 7. Error handling

**No network when the app starts.** The app asks the service before loading
anything. If nothing answers, it shows:

> *No se puede conectar con QuattreTV. Reintentando en N s… Comprueba que la
> television tiene internet.*
> ("Cannot connect to QuattreTV. Retrying in N s… Check that the TV has
> internet.")

with a *Reintentar* button that holds the focus, so OK retries at once.

The app also retries by itself, with growing waits of 2, 4, 8 and 15 seconds,
and it listens for the TV's own "network is back" event so it reconnects the
moment the TV regains connectivity, without the user pressing anything. This
covers the common case of the app starting before the Wi-Fi has finished
associating.

**Service unreachable.** Same screen and same behaviour. The app keeps a list of
service addresses and tries them in order, remembering which one answered last.

**A channel fails to play.** A message is shown on screen and the user stays in
the app, on the channel list. The app never leaves a black screen.

---

## 8. Privacy and data

The app stores on the TV only:

- the address of the service that answered last, so the next start is faster.

It does not read, collect or transmit any personal data of its own, and it uses
no webOS system API — `requiredPermissions` is deliberately absent from
`appinfo.json`. Account data is held by the service under the subscription the
customer signed.

Privacy policy: **https://iptv2.quattre.com/privacy/** (same page in Spanish at
`/privacidad/`). It is public, needs no sign-in and loads nothing from third
parties.

---

## 9. What the app does not do

- No advertising.
- No in-app purchase or payment of any kind.
- No user-generated content.
- No link that leaves the app or opens a browser.
- No social network, no login with a third-party account.
