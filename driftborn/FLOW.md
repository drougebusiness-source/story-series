# DRIFTBORN: branch map (episodes 1-4)

**Path codes:** each vote adds a letter. ⚡ = the choice moves the CURRENT meter. ☠ = deadly: plays out, then REWINDS.
All paths rejoin at **Episode 4, "Prefect Holt"**, then follow `SEASON1.md` from ep 4.

```mermaid
flowchart TD
  E1["EP1 Scrap<br/>Diving a crashed freighter, Kael hears the Current<br/>and finds a sealed Unbound data core"] --> V1{"VOTE 1"}
  V1 -->|"A: sell it to the Concord"| A["EP2 The Reward<br/>Prefect Holt pays him: a ticket off Hollow.<br/>Next day, a Concord gunship flies toward Sola's village"]
  V1 -->|"B: hide it"| B["EP2 The Hum<br/>At night the core starts humming,<br/>and Wick, the dead mining robot, wakes up"]
  A --> V2A{"VOTE 2"}
  V2A -->|"A: take the ticket and go"| AA["EP3 Departure Gate<br/>A masked hunter scans the line for the Attuned.<br/>Kael's Current flares"]
  V2A -->|"B: warn Sola"| AB["EP3 Too Late<br/>He gets there in time to save people,<br/>not the village. Sola learns why"]
  B --> V2B{"VOTE 2"}
  V2B -->|"A: open the core ⚡"| BA["EP3 Distress Call<br/>A hologram: Captain Iva Rhoss, shot down.<br/>Her fighter is falling toward Hollow now"]
  V2B -->|"B: bury it in the dunes"| BB["EP3 Patrol<br/>Concord scanners sweep the scrapyard.<br/>The buried core is still humming"]
  AA --> V3AA{"VOTE 3"}
  V3AA -->|"A: hide the Current ⚡"| AAA["Kael gets on the ship, but<br/>the hunter keeps his face"]
  V3AA -->|"B: run"| AAB["The ticket is lost.<br/>He's a wanted Attuned now"]
  AB --> V3AB{"VOTE 3"}
  V3AB -->|"A: tell Sola the truth"| ABA["She hits him, then asks him<br/>to help her fight back"]
  V3AB -->|"B: blame the Concord, keep the secret"| ABB["She trusts him. For now"]
  BA --> V3BA{"VOTE 3"}
  V3BA -->|"A: reach the crash site first"| BAA["Kael finds Iva alive,<br/>and her fighter can be fixed"]
  V3BA -->|"B: let the Concord find her"| BAB["Iva is captured,<br/>and Holt wants to know who opened the core"]
  BB --> V3BB{"VOTE 3"}
  V3BB -->|"A: lead the patrol away"| BBA["A chase through the dunes.<br/>Holt notices the brave scrap kid"]
  V3BB -->|"B: hide inside the Current ⚡ ☠"| BBB["☠ He goes too deep, and the Current takes him.<br/>REWIND to A"]
  AAA & AAB & ABA & ABB & BAA & BAB & BBA --> M["EP4 Prefect Holt<br/>Holt invites Kael to dinner. He knows.<br/>(SEASON1 ep 4)"]
```

## Episode beats

**EP1 Scrap (everyone).** Hollow, a rust-red mining moon under the ringed giant Veyra. Kael Torvin, 19, dives crashed
ships for parts with his partner Sola. Inside a dead freighter he hears it: **the hum**. No one else ever does. It leads
him to a sealed **Unbound data core**. The Concord pays well for those.
**VOTE 1:** A: sell it to the Concord. B: hide it.

**EP2-A The Reward.** Prefect Holt, polite as ever, pays him a ticket off Hollow. The next morning a Concord gunship heads
for the coordinates in the core: **Sola's village**.
**VOTE 2:** A: take the ticket and go. B: race to warn Sola.

**EP2-B The Hum.** In his shack at night, the core starts to hum in time with him, and **Wick**, the 300-year-old mining
robot rusting in the corner, opens its one teal eye.
**VOTE 2:** A: open the core (⚡ +1). B: bury it in the dunes.

**EP3-AA Departure Gate.** The boarding line. A masked Concord hunter, **the Silent One**, scans each face for the
Attuned. Kael's Current flares.
**VOTE 3:** A: hide the Current (⚡). B: run.

**EP3-AB Too Late.** He saves people, not the village. Sola works out where the Concord got the coordinates.
**VOTE 3:** A: tell Sola the truth. B: blame the Concord and keep the secret.

**EP3-BA Distress Call.** The core plays a hologram from **Captain Iva Rhoss** of the Unbound, shot down. Her fighter is
burning across Hollow's sky right now.
**VOTE 3:** A: reach the crash site first. B: let the Concord find her.

**EP3-BB Patrol.** Concord scanners sweep the scrapyard, and the buried core is still humming.
**VOTE 3:** A: lead the patrol away. B: hide inside the Current (⚡ ☠).

**☠ death:** BBB, Kael goes too deep into the Current and doesn't come back (the frame floods teal, then black). REWIND
to A.

**EP4 Prefect Holt (rejoin).** On every path Holt has noticed Kael. He invites him to dinner and lets him know he knows.
Continue with `SEASON1.md` ep 4.
