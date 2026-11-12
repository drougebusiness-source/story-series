# THE LAST DRAFT: branch map (episodes 1-4)

**Path codes:** each vote adds a letter (`A`, then `A-B`, ...). ☠ = a deadly option: it plays out, then REWINDS.
All paths rejoin at **Episode 4, "St. Agnes"** (the hospital), then follow `SEASON1.md` from ep 4.

```mermaid
flowchart TD
  E1["EP1 Day 731<br/>The fortified high school. Cole sees Dani<br/>in long sleeves in the heat"] --> V1{"VOTE 1"}
  V1 -->|"A: tell the group"| A["EP2 Quarantine<br/>The group panics. Rook raises his rifle:<br/>we end it now"]
  V1 -->|"B: keep her secret"| B["EP2 The Secret<br/>Dani shows Cole the wound:<br/>a dog bite, I think. Her fever is rising"]
  A --> V2A{"VOTE 2"}
  V2A -->|"A: let Rook handle it ☠"| AA["☠ One shot. Dani falls.<br/>Then Priya sees the wound: teeth marks, a DOG.<br/>She was never infected. REWIND to B"]
  V2A -->|"B: lock her in the chem lab,<br/>find medicine"| AB["EP3 The Lab<br/>Priya says the only antibiotics<br/>are at St. Agnes hospital, 6 miles out"]
  B --> V2B{"VOTE 2"}
  V2B -->|"A: tell Priya, the medic"| BA["EP3 Priya Knows<br/>It's infected, not turned.<br/>She needs antibiotics in 24 hours"]
  V2B -->|"B: treat it yourself, tell no one"| BB["EP3 Chemistry<br/>Cole brews a crude antiseptic.<br/>Owen catches him in the lab"]
  AB --> V3AB{"VOTE 3"}
  V3AB -->|"A: go tonight"| ABA["Night run with Cole, Priya and Tank"]
  V3AB -->|"B: wait for morning ☠"| ABB["☠ By dawn Dani's fever is too high.<br/>She doesn't wake up. REWIND to A"]
  BA --> V3BA{"VOTE 3"}
  V3BA -->|"A: Cole and Priya go alone"| BAA["Two-person run, the group is left<br/>with Rook in charge"]
  V3BA -->|"B: tell everyone and go together"| BAB["Whole-group run, the school is left empty"]
  BB --> V3BB{"VOTE 3"}
  V3BB -->|"A: let Owen in on it"| BBA["Owen knows a way to St. Agnes,<br/>for a price"]
  V3BB -->|"B: threaten Owen into silence"| BBB["Owen keeps quiet, for now.<br/>The group starts to crack"]
  ABA & BAA & BAB & BBA & BBB --> M["EP4 St. Agnes<br/>The hospital run<br/>(SEASON1 ep 3 onwards)"]
```

## Episode beats

**EP1 Day 731 (everyone).** The fortified high school, two years after the end. Cole Mercer, chemistry teacher, runs
the place like a classroom: roll call, chores, lessons. Supply-run day. He notices Dani wearing long sleeves in 90-degree
heat and flinching when Tank bumps her arm.
**VOTE 1:** A: tell the group Dani is bitten. B: keep her secret and watch her.

**EP2-A Quarantine.** Panic in the gym. Rook steps forward with his rifle: *"Rules are rules. We end it now."* Dani is
crying that it isn't what they think.
**VOTE 2:** A: let Rook handle it ☠. B: lock her in the chem lab and look for medicine.

**EP2-B The Secret.** Alone in the lab, Dani rolls up her sleeve: a ragged wound. *"A dog, I think. Three days ago."* Her
skin is hot, and the edges are red and spreading.
**VOTE 2:** A: tell Priya, the medic. B: treat it yourself and tell no one.

**EP3-AB The Lab.** Dani behind the lab's glass door. Priya's verdict: it's infection, not the virus, but without real
antibiotics she has a day. The nearest are at St. Agnes, six miles through the dead.
**VOTE 3:** A: go tonight. B: wait for morning ☠.

**EP3-BA Priya Knows.** Priya confirms it's a dog bite gone septic, and gives them 24 hours.
**VOTE 3:** A: Cole and Priya go alone (leaving Rook in charge). B: tell everyone and go together.

**EP3-BB Chemistry.** Cole improvises an antiseptic from the old supply closet. It buys time, not a cure. Owen walks in.
**VOTE 3:** A: let Owen in on it (he knows a back way, for a price). B: threaten Owen into silence.

**☠ deaths:** AA, Rook shoots Dani, and only then do they see it was a dog bite: the guilt that rewinds. ABB, waiting
until morning costs Dani her life. Both rewind to the other option.

**EP4 St. Agnes (rejoin).** Every path ends at the hospital. Who's there depends on the votes. Continue with `SEASON1.md`
ep 3 ("St. Agnes") onwards.
