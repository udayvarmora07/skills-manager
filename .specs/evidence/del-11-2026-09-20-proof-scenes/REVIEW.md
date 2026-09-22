# DEL-11 external screenshot candidate packet

**Status: PENDING HUMAN REVIEW**

These are dated current-build candidates for external communication. They are
not approved publication evidence until a human reviewer completes the
decision section below.

## Provenance

- Capture date: 2026-09-20
- Source build commit: `ebaf6ebbad4a191ba6dbde555d0fa7d732a8d99a`
- Source page viewport: 1280x900
- Fixture root: `/tmp/skills-manager-external-demo-20260920` (owner-only,
  disposable, synthetic)
- Fixture: disposable synthetic scopes, skills, project, history, and
  validation data; no participant data or private skill content
- Page capture: fresh headless Chromium/CDP sessions against the current
  `WebAppServer`; one fresh browser profile per scene
- Labeling: Pillow 10.2.0 added the footer to the `external-*.png` copies;
  the application and runtime dependencies were not changed
- Operator-tool research: [Flameshot](https://github.com/flameshot-org/flameshot)
  14.0.0 is installed at `~/.local/bin/flameshot` without sudo. Its full-screen
  trial was rejected for publication because it included the desktop panel and
  capture notifications; it remains suitable for a human operator's manual
  selection or annotation workflow.

## Candidate scenes

| Scene | Raw page capture | Labeled candidate | What it shows |
|---|---|---|---|
| Logical Library | `logical-library-2026-09-20.png` | `external-logical-library-2026-09-20.png` | One logical skill with three observed physical copies and divergent-content markers |
| Effective-state evidence | `effective-state-2026-09-20.png` | `external-effective-state-2026-09-20.png` | Accepted disposable project observation plus documented and unknown adapter precedence |
| Quality and trust | `quality-trust-2026-09-20.png` | `external-quality-trust-2026-09-20.png` | Valid synthetic skill with an advisory validation warning |
| Recovery | `recovery-2026-09-20.png` | `external-recovery-2026-09-20.png` | History entries and a recoverable snapshot/rollback action |

## SHA-256

| File | SHA-256 |
|---|---|
| `logical-library-2026-09-20.png` | `51ad76ac7d285977d86166b88448c850118e309d329fcdf5d45369201a9c8a42` |
| `effective-state-2026-09-20.png` | `c944f3a084ecb3b7b338db7e1a8042d4bed831211f0c66d0764bf0a0a2bd8987` |
| `quality-trust-2026-09-20.png` | `581a24b3172402aba4b6b6636532eb4530cd2ab39c340e9a9cc8f22e07aaa19f` |
| `recovery-2026-09-20.png` | `13470c7b8f7b243aa44ca050c8549d6fe6b346c93429f0b24dabbe489f0dad90` |
| `external-logical-library-2026-09-20.png` | `b5860931f00dc4ba898736c3823ff93a58b19f53d8251e22c5a632d679711b2f` |
| `external-effective-state-2026-09-20.png` | `58d5759d4ba75127e574e61e65a255fee86bf07201cc5b40c5a7bebab3c93709` |
| `external-quality-trust-2026-09-20.png` | `626b14a813120d570d121695f7a0a190a73c2b5b6b1d3d40856a179e92fc1cdd` |
| `external-recovery-2026-09-20.png` | `74cbf74638df88dec768e56cbf2ca0769384c0fbfc8fe18c3708279843e3ec67` |

## Human review checklist

- [ ] Open all four labeled candidates at native dimensions.
- [ ] Confirm the footer's build/date/viewport labels match the intended
  communication context and do not imply participant or adoption evidence.
- [ ] Confirm the four visible scenes are accurate, understandable, and free
  of private skill bodies, prompts, credentials, telemetry, or identifying
  data.
- [ ] Confirm the synthetic fixture is acceptable for the intended external
  audience, or request recapture with a different disposable fixture.
- [ ] Record the reviewer, date, decision, and publication destination below.

## Human decision

- Reviewer: _pending_
- Review date: _pending_
- Decision: _pending — approve / reject / request recapture_
- Publication destination: _pending_
- Notes: _pending_
