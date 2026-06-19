# Demo Narration Template

**Status:** Phase 32 (Demo Suite Polish) — written before any demo is refactored (per P8 pitfall prevention).
**Audience:** Demo authors adding new demos to `demos/`.
**Compliance test:** `tests/test_demos.py::TestNarrationTemplate::test_all_demos_follow_template` (Plan 03).

## 5-Stage Structure

Every demo narration MUST use exactly these five stages, in this order. Stage headings must be the literal section names below (the regression test greps for them).

1. **Setup** — Introduce the scene: tissue type, instrument(s), goal of the task. Use present tense. Name the named bodies (e.g., "skin_patch_left", "knot_driver") so the reader can correlate narration to scene JSON.
2. **Action** — Describe the policy's first observable behavior (approach, pick-up, transport). One or two sentences.
3. **Critical Moment** — The hardest sub-step where most policies fail. The takeaway of the demo lives here.
4. **Outcome** — What success looks like (suture tied, knot tightened, needle through target). Be specific; cite the scene body's success criterion if the JSON defines one.
5. **Takeaway** — One sentence the reader remembers. No hype. State what the demo demonstrated, not what the user should feel.

## Per-Stage Constraints

- 1-2 sentences per stage.
- ≤25 words per sentence (the regression test counts words).
- Stage headings must match the literal markdown above (`## Setup`, `## Action`, ...).
- Stages appear in the listed order; no reordering, no extra stages.

## Vocabulary Rules

- **Avoid first-person** ("we", "I", "you"). Use "the agent", "the policy", or the named body.
- **Name scene bodies** ("the curved_suturing_needle", "the knot_driver") instead of generic nouns ("the needle", "the tool").
- **Use present tense** for ongoing actions ("the policy approaches"), past tense for completed outcomes ("the suture is complete").
- **No marketing language** ("amazing", "incredible", "seamless"). State observable facts.

## Example — Suturing Walkthrough

```markdown
## Setup
The agent operates the surgical_arm_1 gripper inside a suturing scene with two skin_patch tissues and one curved_suturing_needle. The task: connect both patches with a single suture.

## Action
The policy approaches the curved_suturing_needle from above, closes the gripper jaws on the needle's shaft, and lifts it 5 cm above the tissue plane.

## Critical Moment
The needle's arc must clear both skin_patch edges simultaneously; off-axis entry tears the FEM mesh. The policy maintains a 15° entry angle.

## Outcome
The needle passes through skin_patch_left and skin_patch_right in a single arc. The gripper releases; the suture is complete.

## Takeaway
Suturing rewards dense distance shaping plus a sparse success bonus, training in roughly 50k PPO timesteps on a single CPU.
```

## Anti-Patterns

- ❌ "Now let's see how the agent performs!" (first-person, hype)
- ❌ "The needle is picked up and then transported to the tissue and then..." (run-on, no stage markers)
- ❌ "Amazing! The policy succeeded with flying colors!" (marketing language)
- ❌ Skipping the Critical Moment stage because the demo is "too simple"

## How to Add a New Demo

1. Add your scene JSON to `scenes/{task}.json` (or `tests/fixtures/scenes/{task}.json` if the scene is test-only).
2. Create `demos/{task}_demo.py` following the structure in `demos/suturing_demo.py`.
3. Import helpers from `demos._common`: `print_banner`, `print_scene_info`, `resolve_scene`, `format_narration_step`.
4. Write a 5-stage narration block in the demo's main() that follows this template verbatim.
5. Add a regression test to `tests/test_demos.py::TestDemoRegression` that runs `python demos/{task}_demo.py --headless --steps 0` as a subprocess and asserts exit 0 + expected banner substring.
6. Run `pytest tests/test_demos.py -v` — the narration-compliance test (Plan 03) will fail if your demo drifts from the template.