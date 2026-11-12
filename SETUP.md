# Your part: setting up the 4 story accounts

About 15 minutes per account, once. Do them in this order. Nothing posts until Claude switches a series to `live: true`.

| Series | Name on Instagram | Handle | Profile picture | GitHub secret suffix |
|---|---|---|---|---|
| COMPLIANT | COMPLIANT \| You Decide | **`citizen.213`** ✅ made | `images/compliant-profile.png` | `CITIZEN213` |
| THE LAST DRAFT | THE LAST DRAFT \| You Decide Who Lives | **`lastdraft.survival`** ✅ made | `images/last-draft-profile.png` | `LASTDRAFTSURVIVAL` |
| ROLL FOR FATE | ROLL FOR FATE \| You Choose, Dice Decide | **`roll.for.fate`** ✅ made | `images/roll-for-fate-profile.png` | `ROLLFORFATE` |
| DRIFTBORN | DRIFTBORN \| You Decide His Fate | **`driftborn.saga`** ✅ made | `images/driftborn-profile.png` | `DRIFTBORN` |

Bios are in each series' `BRAND.md` (copy them as written).

## 1. Make each Instagram account (phone, about 5 min each)
1. Instagram → your profile → tap your username at the top → **Add Instagram account** → **Create new account**.
2. Pick the handle and name from the table. Use the profile picture from `images/`.
3. **Settings → Account type and tools → Switch to professional account → Creator →** category **Digital creator**.
4. Paste the bio from `BRAND.md`. Leave the link empty for now.
5. **Don't post anything yet.** The pinned posts go up at launch.

## 2. Give each account its own Facebook Page (computer, about 3 min each)
1. facebook.com → **Pages → Create new Page**. Name it the same as the series (e.g. "COMPLIANT"). Category: "Digital creator".
2. On the new Page: **Settings → Linked accounts → Instagram → Connect** and log in to that series' Instagram account.

## 3. Let the pipeline post (computer, about 5 min each)
Use the same Meta app that already posts JIC (developers.facebook.com → My Apps).
1. Open **Graph API Explorer** (Tools menu). Choose JIC's app.
2. **User or Page → Get Page Access Token**, and when asked which Pages, tick the 4 new ones (keep JIC's ticked too).
3. Make sure these permissions are on the list, then **Generate Access Token**:
   `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `pages_show_list`,
   `pages_read_engagement`, `business_management`.
   (`instagram_manage_comments` is new: it's how votes are counted.)
4. In the Explorer, run `me/accounts?fields=name,access_token,instagram_business_account`. For each of the 4 Pages
   you'll see its **access_token** and its **instagram_business_account id**.
5. To make the tokens long-lived, do it the same way as JIC's token on Oct 30 (a Page token from a long-lived user
   token doesn't expire).

## 4. Put the keys into GitHub (computer, about 5 min total)
In the `story-series` repo: **Settings → Secrets and variables → Actions → New repository secret.**
For each series (suffix from the table), add two secrets:
- `IG_USER_ID_<SUFFIX>` = the instagram_business_account id
- `META_PAGE_TOKEN_<SUFFIX>` = that Page's access_token

Then add **`GEMINI_API_KEY`**, the same key JIC uses. **Never paste keys or tokens into chat.**

## 5. Check it (1 min)
**Actions → Check connections → Run workflow.** You should see 4 lines like `COMPLIANT: ✅ connected to @compliant.series`.
Tell Claude the 4 handles.

## 6. Approve episode 1 (after the Nov 22 reset and your Gemini top-up)
**Actions → Preview episode → Run workflow**, once for each series. Each run leaves a video under **Artifacts**.
Watch them and tell Claude "approved", or what to change. What you approve is exactly what goes up.

## 7. Launch day
Claude posts the 2 pinned images on each account (`images/<series>-pin1.png` and `-pin2.png`; you pin them) and sets
`live: true`. Episodes then go out Mon/Wed/Fri at 6, 7, 8 and 9 PM Central, and the 30-day test starts.

## Money
- Gemini (art and writing): about **$10-20/month** for all 4 series. Top up the same Gemini account JIC uses.
- GitHub Actions: about 5 minutes per episode × 12 a week ≈ 250 minutes a month. That's inside the free private-repo
  minutes, but JIC's private repos share the same allowance, so Kevin should keep an eye on it.
- Instagram and Facebook: free.
