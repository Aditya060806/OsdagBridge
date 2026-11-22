Pass the deck concrete modulus to the deck slab design in MPa (fixes #148)
Fixes #148

## Problem
`ConcreteProperties.Ecm` is stored in GPa (`dto.py`, 33.0 for M40). `PlateGirderBridge.design_deck_slab()` passed it unchanged to `deckdesign.design_deck_slab()`, which documents `Ecm` in MPa and computes the modular ratio as `alpha_e = Es / Ecm` in `_cracked_section()`. Every deck SLS check therefore ran with αe = 6061 instead of 6.06, and the cracked neutral axis sat almost on the bottom bars (x/d = 0.976 instead of 0.182).

## Change
`plategirderbridge.py`, `design_deck_slab()`: convert GPa to MPa before the call. `designer.py` already applies the same conversion for the girder design (L336-L337). The DTO keeps its GPa unit, so nothing else changes.

## Effect
Full design of the inputs captured from my GUI runs in #148, on unmodified `dev` and on this branch:

| TC01: M40, Fe 500, 250 mm deck | `dev` | this PR |
|---|---:|---:|
| Bottom bars | Ø12 @ 175 (646 mm²/m) | Ø12 @ 185 (611 mm²/m) |
| Concrete stress, bottom (MPa) / UR | 2.49 / 0.13 | 9.84 / 0.51 |
| Steel stress, bottom (MPa) / UR | 365.3 / 0.91 | 276.9 / 0.69 |
| Crack width bottom / top (mm), limit 0.3 | 0.198 / 0.213 | 0.263 / 0.281 |

TC05 (custom concrete, Ecm 33.5 GPa) and TC09 (Custom mode, 230 mm deck) change the same way. All deck checks still pass in the three cases (highest deck UR 0.99, 0.99 and 0.95). The girder `util.*` values do not change. In `design_results` only the deck reinforcement area used by the composite checks and the values derived from it change (TC01: 11.38 to 11.03 cm²/m, transverse shear capacity 370.24 to 370.13 kN/m).

## Tests
`tests/unit/test_deck_ecm_units.py` runs `design_deck_slab()` for an M40 / Fe 500 deck with the `deckdesign` call captured. It checks that the call receives Ecm = 33 000 MPa, and that `_cracked_section()` then gives αe ≈ 6.06 and x ≈ 35.3 mm for the default bottom mat. It fails on `dev` (Ecm = 33.0) and passes here. `pytest tests/` passes (6 tests).

Not in this PR: the Concrete Results Table / Excel export reads the same GPa value (#171).

Tested on Windows 11, Python 3.12.16.
