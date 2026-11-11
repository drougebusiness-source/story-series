# Story Series: 4 vote-driven Instagram accounts

Status (2026-11-11): **built, waiting to launch.** Launch after the Nov 22 ElevenLabs credit reset, when the owner
adds money for it. Nothing is posted or spent yet.

| Series | Genre | Main character | Folder |
|---|---|---|---|
| THE LAST DRAFT | Zombie survival group | Cole Mercer, chemistry teacher | `last-draft/` |
| ROLL FOR FATE | D&D-style fantasy party | Wren Ashby, disgraced squire | `roll-for-fate/` |
| COMPLIANT | Dystopia: rebel or builder | Ezra Vale, Ministry data clerk | `compliant/` |
| DRIFTBORN | Original space opera | Kael Torvin, scrap diver | `driftborn/` |

Each folder has `BRAND.md` (handles, bio, look, voice, cast) and `SEASON1.md` (10 episodes with the branches).
`images/` has a profile picture and the 3 pinned posts for each account. Rebuild them with `python make_images.py`.

---

## How every series works (same rules on all 4)

**Episode:** one Reel, 45-75 s, vertical 9:16. Story beats, then a cliffhanger choice on screen.
**Vote:** the caption and the last frame say **"Comment A or B. Voting closes in 24 h."** Some big moments have a C.
**Count:** after 24 h, count A/B/C comments (one vote per account, the latest one counts). Most votes wins.
**No votes or a tie → the AI picks**, by what makes the best story *and* fits the character so far. The next episode
opens with who decided: **"YOU CHOSE B (63%)"** or **"NO VOTES. THE STORY CHOSE A."** Always say it; never fake votes.
**Death:** any character can die, the main one included. A death ends that branch. The next episode is a
**"REWIND"**: "That's how it ends. Back to the choice." The *other* option then plays out. Deaths are shown cartoon-style
and off screen (a cut to black, a sound), never gore. That keeps Reels from being limited.
**Story memory:** each series keeps a running `CANON.md` (choices made, who's alive, what the character believes) so
the AI never contradicts the past.
**Recap:** every 10th episode is a 30 s "Previously on..." recap with the vote results. Good for new followers.

## Posting plan

- **3 episodes a week per account**: Mon, Wed, Fri (post), with votes closing on Tue, Thu and Sat/Sun.
  Stagger the accounts by an hour (6, 7, 8 and 9 PM Central) so they don't compete with each other or JIC.
- **Votes are comments only.** Instagram's API can't post Story poll stickers or read their results, so Story polls
  would be a manual chore. Skip them.
- **Pinned posts (3 per account, made in `images/`):** 1. "Meet the character", 2. "How this works: you decide",
  3. Episode 1.
- **Captions only to start** (music + sound effects, on-screen text). No narration needed. If a series wins the test,
  add a voice for the main character only.

## Account setup (owner, about 10 minutes per account, once)

1. In Instagram, add an account (one login can switch between up to 5). Use a handle from that series' `BRAND.md`.
2. Settings → Account type → switch to **Professional → Creator**. Category: "Digital creator".
3. Profile picture: `images/<series>-profile.png`. Name and bio: copy from `BRAND.md`.
4. Link a Facebook Page to it (needed later so the pipeline can post and count votes). One new Page per account.
5. Post the 3 pinned posts in order (`-pin1`, `-pin2`, then episode 1 at launch) and pin them.
6. Tell Claude the 4 handles. Claude adds them to the office and the posting plan.

## The 30-day test

Starts the day episode 1 goes up on all 4. After 30 days, **keep** any series with **300+ followers or an average of
1,000+ views per episode**. Pause the rest; their canon is saved so they can come back. Put the freed effort and voice
budget into the winners.

## Budget (owner adds money for this)

| Item | Cost | Notes |
|---|---|---|
| Instagram accounts and Facebook Pages | $0 | |
| Art for episodes | about $10-20/month | Gemini images (the same tool JIC uses), about 4¢ each. About 8 per episode × 12 a week ≈ 100 a week; reusing scenes cuts that |
| Voice (optional, winners only) | ElevenLabs credits | not needed for the test: captions only |
| Metricool tracking | check plan | the current plan may not cover 4 more brands; Ana can read Instagram directly instead |

## Automation: how it runs with no daily work

```
 Mon 6 PM  ── GitHub Action: write episode from CANON.md ─▶ Gemini art ─▶ build Reel ─▶ post to Instagram
 Tue 6 PM  ── GitHub Action: read the episode's comments ─▶ count A/B ─▶ (no votes? AI picks) ─▶ save to CANON.md
 Wed 6 PM  ── next episode opens with "YOU CHOSE B (63%)" ... and so on, for all 4 accounts
```

- **Where it lives:** a new GitHub repo, `story-series`, next to `doodle-explainers` (JIC). It reuses JIC's video
  builder, Gemini art and Instagram posting code. It runs on GitHub's schedule (the same as JIC), so the PC doesn't
  need to be on.
- **Posting:** Instagram's API can't schedule posts, so the Action posts at the time itself (JIC does the same).
  A Reel is uploaded straight to Instagram, then published (no public link needed). Instagram limits API posts per account per day, far above 3 a week.
- **Vote counting:** after 24 h the Action reads the Reel's comments through the API. It counts the first A/B/C in each
  comment, one vote per account (the latest one counts), and ignores the account's own comments.
- **Writing:** Gemini writes the episode script from `BRAND.md`, `SEASON1.md`, `CANON.md` and the vote (the newest
  Gemini "flash" model, so no extra AI account is needed). The code checks the length, the scenes and the choice, and
  asks again if anything is off.
- **The office:** each account gets a row on the Performance tab (followers, views per episode, votes per episode) and
  a spot on the health light, like JIC.

### What the owner sets up (once)
1. **The 4 Instagram accounts**, each switched to Professional → Creator and linked to its own Facebook Page.
2. **Add the 4 Pages to JIC's existing Meta app** (the one that already posts JIC). No new app needed. Then generate a
   **Page token for each Page**, the same way as the JIC token (2026-10-30), with these permissions:
   `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `pages_show_list`,
   `pages_read_engagement`, `business_management`. Comment reading (`instagram_manage_comments`) is new: JIC's token may
   not have had it.
3. **Paste each token into the new repo's GitHub secrets** (Claude says the exact names). Tokens never go in chat or files.
4. **Money:** top up Gemini for the art (about $10-20/month for all 4). Voice is optional.

### Getting everything ready (order)
1. ✅ Brand kits, season plans, profile pictures, pinned posts (this folder).
2. Owner: make the 4 accounts, link Pages, add them to the Meta app (steps above).
3. Claude: build the `story-series` repo (episode pipeline, vote counter, posting) and a "check connections" workflow
   that tests each token without posting.
4. Claude: make episode 1 of each series and send it for the owner's OK before anything goes public.
5. After the Nov 22 reset and the top-up: launch all 4 on the same day. The 30-day test starts.

## Built (2026-11-11)
The pipeline is in `stories/` (see `SETUP.md` for the owner's part). Workflows: Episode (the schedule), Preview
episode, Check connections, Tests.

## Was planned

- The episode pipeline: script → images → Reel → post (reuse the JIC pipeline's video and posting parts).
- The vote counter: read comments through the Instagram API at the 24 h mark, apply the rules above, write the result
  into `CANON.md`.
- A slot for each account in the Agent Office (Performance tab and health light).
