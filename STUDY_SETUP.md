# Running the learning-gains study

Your claim: the system's explanations improve learning. Your test: students take an adaptive
test, learn with the system, then take a second adaptive test — and you measure whether they
climb higher the second time.

This guide sets that up. It assumes the app is deployed (`DEPLOY_RENDER_SUPABASE.md`) and your
question bank is ready (see the warning in Step 2).

---

## The design in one picture

```
              ── THE EVALUATION (DBMS subject viva) ──

PRE-TEST                  student studies                POST-TEST
DBMS approved bank        with the system                DBMS approved bank
adaptive                  (explanations,                 adaptive
NO explanations            study cards)                  + explanations after each answer
NO remediation                                           + remedial second chances
     │                                                        │
     └──────────── compare primary scores ────────────────────┘

              ── SEPARATE FEATURE, NOT EVALUATED ──

PROJECT VIVA   submit report → concepts → study cards → adaptive test on your own project
```

**Both evaluated tests draw the same DBMS bank.** That is the point: if the pre-test and
post-test pulled from different sources, any difference could be the material rather than
the teaching. Same bank, same concepts, same adaptive engine — the only thing that changes
is whether the student got explanations and second chances.

**Project viva is a working feature but sits outside the study.** Each student's project is
different, so their scores aren't comparable to each other or to a shared baseline.

### The three test types

| Test type | Questions from | Adaptive | Explanations | Remediation | In the evaluation |
|---|---|---|---|---|---|
| `pre_test` | approved DBMS bank | yes | **no** | **no** | yes — baseline |
| `post_test` | approved DBMS bank | yes | yes | yes (0.25) | yes — outcome |
| `project_viva` | student's own report | yes | yes | yes (0.25) | no |

The app will refuse to save a `pre_test` with inline explanations switched on — a baseline
that teaches isn't a baseline.

- **Both tests adaptive** — correct answers push the level up, wrong ones down. The outcome is
  *how high they climb* and *their readiness score*, not a raw mark. This is the honest test of
  your claim.
- **Test 1 shows no answers or explanations.** If it did, the baseline test would itself teach,
  and you couldn't separate "the system taught them" from "the first test taught them."
- **Test 2 shows everything** — that's where the system's teaching is delivered.
- **No question repeats across the two tests** (the `study_group` tag handles this), so an
  improvement can't just be "I remember this exact question."

---

## Step 1 — The roster (your 20 friends)

Your friends don't have college register numbers, so **you assign simple IDs.** Whatever you
put in the roster is what's valid — it's the source of truth.

Make `roster.csv`:

```csv
register_number,full_name,email,department,section
STUDY01,Aditya R,aditya@gmail.com,CSE,A
STUDY02,Priya S,priya@gmail.com,CSE,A
STUDY03,Karan M,karan@gmail.com,CSE,A
STUDY04,Sneha T,sneha@gmail.com,CSE,A
```

…through STUDY20. Use each friend's **real email** — it must match exactly at registration
(lowercase, no typos).

Import it: teacher login → **Students & accounts → Import eligible students** → pick the file.
Or `python scripts/import_students.py roster.csv`.

That `STUDYnn` ID becomes each person's label in your results CSV, so it's how you'll match
their Test 1 to their Test 2 when computing gains. Keep the roster file — it's your key.

### The message to send each friend

> Hi! For the viva-system study, your login ID is **STUDY07**.
> 1. Go to https://viva-platform-xxxx.onrender.com/register
> 2. Register number: **STUDY07**, email: **your.exact@email.com** 
>    pick any password (10+ chars, a letter and a number).
> 3. I'll approve you, then you can log in.
> First page may take a minute to load — that's normal.

Send each person their **exact** email string — mismatches are the #1 registration failure.

After they register, approve them: teacher → **Students & accounts** → Approve. (Pending
accounts can't log in — that's the second gate.)

---

## Step 2 — ⚠️ The question bank must be ready first

Both tests are adaptive, so a student can climb to Level 5. That means **every level you allow
(0 up to `max_level`) needs a real pool of questions**, and Test 1 + Test 2 together need
**enough that they never overlap.**

**Both evaluated tests now pull from the same bank with no repeats between them**, so the
bank has to be deep enough for two disjoint runs. This is the binding constraint on your
study — not the code.

Rule of thumb for a clean study, per concept you test:

```
~8–10 approved questions per level, at every level 0..max_level
```

Two concepts × 4 levels (0–3) × ~9 ≈ **72 approved questions minimum.** If you allow levels
0–5, more. Your current bank (25 questions, 4 concepts, ~1 per level) is **not enough** — a
student will exhaust a level and the test ends early, and Test 2 will be forced to reuse
Test 1 questions.

Build it up first:

```powershell
$env:GROQ_API_KEY = "gsk_..."
python scripts/generate_questions.py DBMS --levels 0 1 2 3 --per-level 10
```

Then **approve** them (teacher → Question bank → `generated` tab). A human reads each one —
the validator catches broken structure, not plausible-but-wrong content.

If you can't get Levels 4–5 to good quality, **set `max_level = 3`** on both exams and cap the
climb there. A clean 4-level study beats a noisy 6-level one.

Don't schedule the tests until the blueprint pages show green.

---

## Step 3 — Create Test 1 (baseline)

Teacher → **Exams → Create exam**:

| Field | Value | Why |
|---|---|---|
| Title | `Test 1 — Baseline` | |
| **Test type** | **pre_test** | same DBMS bank, no feedback |
| **Show explanations after each answer** | **OFF** | the baseline must not teach |
| Subject | DBMS | |
| Registration window | now → a few days | so they can register anytime |
| **Exam window** | e.g. Mon 00:00 → Wed 23:59 | **wide** — they take it whenever, no coordination |
| Duration | 30 min | the timer once they start |
| Question count | 20 | |
| Starting level | 0 | everyone starts at the bottom |
| Highest level used | 3 (or 5 if L4–5 are good) | the climb ceiling |
| Allow late start | **on** | fine with a wide window |
| Show result immediately | **OFF** | baseline must not teach |
| **Study group tag** | `dbms-study-2026` | **critical — same tag on both tests** |
| Status | active | |

Save → set the **Concepts** (tick which concepts are in scope, set the question count).
There is no per-level grid: the adaptive engine picks the level from how the student answers.

---

## Step 4 — Create Test 2 (post-test)

Same as Test 1, but:

| Field | Value | Why |
|---|---|---|
| Title | `Test 2 — Post` | |
| **Test type** | **post_test** | same DBMS bank, with explanations |
| **Show explanations after each answer** | **ON** | this is the teaching step |
| **Exam window** | Thu 00:00 → Sat 23:59 (starts **after** Test 1 closes) | forces learning in between |
| Show result immediately | **ON** | this is where the system teaches |
| **Study group tag** | `dbms-study-2026` | **same tag → no question reused from Test 1** |

Everything else identical — same subject, starting level, max level, question count. Matching
these keeps the two tests comparable.

> The matching `study_group` tag is what guarantees Test 2 never shows a question the student
> saw in Test 1. That's automatic once both tags are identical.

---

## Step 5 — What "learning between the tests" means

Between Test 1 closing and Test 2 opening, students **use the system** — the Streamlit
Practice/Learn mode, the explanations, the study cards. That's the intervention. Tell them
what to do:

> Between the two tests, spend ~30–45 min in the practice tool going through the concepts and
> reading the explanations after each question. Do Test 2 within 2 days of Test 1, in a quiet
> place, in one sitting.

Writing the structure into the instructions (even without fixing an exact clock time) keeps
the study honest — otherwise one person learns for an hour and another for two minutes, and
your gains measurement is noise.

---

## Scoring: two numbers, and which one to compare

The post-test gives a second chance after a wrong answer — an easier question on the same
concept, worth **0.25**. A first-time correct answer is **1.0**, wrong is **0**.

That produces two scores:

| Score | What it counts | Use it for |
|---|---|---|
| **Primary** | first-attempt questions only | **the pre/post comparison** |
| **Credited** | primary + 0.25 recovery credit | how much they recovered *during* the test |

**Compare the primary scores.** The pre-test has no remediation, so it can't earn recovery
credit — scoring the post-test with a mechanic the baseline never offered would manufacture
a gain that isn't learning. On a test with no remedials the two numbers are identical, which
is exactly why the comparison stays fair.

Remedial questions are also **extra** — they don't consume the question count, so a student
who needs remediation doesn't get a shorter test.

---

## Step 6 — Read the results

After each test: teacher → the exam → **Results → Export CSV.** Each row is one student, keyed
by their `STUDYnn` ID. The columns you care about:

| Column | What it tells you |
|---|---|
| `readiness` | Your **primary outcome.** Weights higher levels more and rewards depth. Computed on primary questions only. |
| `post_credited_score` | Score including recovery credit — report alongside, don't compare on it. |
| `recovery_points` | How much they clawed back after seeing explanations. |
| `cards_read` | Whether they actually studied — a confound worth checking. |
| `highest_level` | Your **headline number** — how far up they climbed. |
| `score_percent` | Raw correctness (secondary). |
| `avg_response_time` | Sanity check — implausibly fast = rushed/guessed. |
| `integrity_flags` | Review indicators only. A flag = a question, not a verdict. |

The teacher dashboard has a **System evaluation** page that pairs each student's two
attempts automatically and exports one CSV with the gains already computed —
`/teacher/evaluation`. You no longer need to match the two CSVs by hand.

**The analysis:** gains are computed per student as

```
gain_readiness  = Test2.readiness      − Test1.readiness
gain_level      = Test2.highest_level  − Test1.highest_level
```

If your claim holds, most students show **positive** gains — they reach higher levels and
higher readiness after using the system. A paired comparison (each student against themselves)
is exactly right here, and it's why the `STUDYnn` matching matters.

Twenty students is small, so report it honestly: mean gain, how many improved vs. didn't, and
a couple of individual traces. Don't over-claim significance from n=20 — show the direction and
size of the effect and let it speak.

---

## A few honest caveats to note in your writeup

- **Unproctored, self-scheduled.** Convenient, but conditions vary between students and between
  the two tests. You traded control for feasibility — say so.
- **Test-retest effect.** Simply taking a test twice can raise scores a little, independent of
  your system. Your defence: no question repeats (the `study_group` tag), so any gain is at the
  *level/concept* understanding, not item memory. Still worth naming.
- **No control group.** You're measuring within-person change, not against students who *didn't*
  use the system. That's fine for a first study — just don't phrase it as proof the system beats
  an alternative.

None of these sink the study. Naming them makes it stronger.

---

## Order of operations

1. Deploy (`DEPLOY_RENDER_SUPABASE.md`)
2. **Build + approve the question bank** — the long pole; both tests depend on it
3. Import roster (STUDY01…20), send invites, approve accounts
4. Create Test 1 (result **off**) and Test 2 (result **on**), **same study_group tag**
5. Test 1 window → students study → Test 2 window
6. Export CSV after each; match on `STUDYnn`; compute readiness and level gains
