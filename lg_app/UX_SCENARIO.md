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
subscriber watch the live TV channels included in their subscription, with a
full programme guide.

Some subscriptions also include a film and series catalogue and personal
recordings. **Those are not enabled on the review account** (see section 2), so
the reviewer will not see them: the app only shows what the account actually
includes, and never displays an option that leads nowhere.

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
| **Password** | ver `ACCESOS.md` (copia local, fuera del repositorio) |
| **Subscription** | Live TV — the 80 channels served to webOS, and the programme guide. Films, series and recordings are **not** enabled on this account, so those menu options do not appear |
| **Expiry** | None. The account does not expire. |
| **Concurrent devices** | 5 |
| **Adult content** | None. See section 6 |

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

Channels can be marked with 🔒 when they are rated for adults. None of the channels served to webOS is. See section 6.

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

Opened with ◄ or BACK from the channel list. A vertical list.

**With the review account the menu shows exactly three options:**

- **Canales** — the channel list
- **Categorias** — filter channels by genre
- **Solo favoritos** — show only the channels the customer marked as favourite

Other subscriptions add **Peliculas**, **Series** and **Mis grabaciones**. The
menu is built from what the account actually includes: an option that does not
apply is not shown at all, never shown disabled and never leading to an empty
screen. That is why the review account sees three and not six.

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
| **OK** | Record the programme, where the subscription includes recordings |
| **◄** / **BACK** | Back to the channel list |

### 4.7 Films, series and recordings — not part of this review

Subscriptions that include them add three more menu options, navigated exactly
like the channel list: ▲▼ to move, OK to play, ◄ or BACK to go back.

**They are deliberately not enabled on the review account.** Rather than show a
reviewer an empty catalogue, the app hides what the account does not include.

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

## 5b. Radio stations

Channels **1001 to 1016 are radio stations**. They carry audio only and have no
video track, which is expected and is not a playback fault.

The app detects them and does not leave the screen black: it shows the station
logo, its name, what is on air and a small animation, over the same area the
video would occupy. This works both in the preview window of the menu and full
screen.

---

## 6. Parental control and adult content

**This app contains no adult material.**

Our television line-up does include one channel rated for adults. It is
**excluded from the webOS line-up on the server**, per device type, so it is not
reachable from this app at all: it is not in the channel list, it is not
returned by the guide, and asking for its address by channel id returns an
error. It remains available on our set-top boxes and Android devices, which are
not distributed through the LG Content Store.

The line-up served to a webOS television has 80 channels. The same account on a
set-top box sees 81.

**The app still ships a PIN mechanism**, unused on webOS today, in case a channel
is rated for adults in the future. It is worth describing because of how it
works:

1. A locked channel appears with a padlock and nothing else.
2. **The stream address of a locked channel is never sent to the TV.** The server
   withholds it. The PIN is not a screen the app draws over the video: it is the
   server refusing to hand over the content, so the lock cannot be bypassed by
   tampering with the app.
3. The preview window does not play a locked channel either.
4. Pressing OK on a locked channel opens the PIN screen. Wrong PINs are
   rate-limited.
5. The PIN is set by the account holder from the customer's web account. It is
   never stored on the television.

**During this review no channel will ask for a PIN**, because none of the 80
channels served to webOS is rated for adults.

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

Privacy policy: **https://quattre.com/avisolegal/** &mdash; published on the
company's own domain, next to the general legal notice, and covering all the
QuattreTV applications. It is public, needs no sign-in and is available in both
Spanish and English.

---

## 9. What the app does not do

- No advertising.
- No in-app purchase or payment of any kind.
- No user-generated content.
- No link that leaves the app or opens a browser.
- No social network, no login with a third-party account.
