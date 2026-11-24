# m0_typeform_maps: maps declared with a type form in From/To (probe P2)

Task t-2026-11-23-mettadinc-m0-typeform-maps. Base: mettadinc main 8ae0fa7 (merge of PR #32, m0-subset-reach).

    python3 tests/dcalc/m0_typeform_maps/run_m0_typeform_maps.py        # release and --beyond-release; 85 gates
    python3 tests/dcalc/m0_typeform_maps/reference_answers.py           # Ben's reference evaluator on the gate fixture

## What the spec says, and the lowering

- Spec 5.1 grammar (mettadinc_language_spec.txt l.1708-1715): `declaration ::= (head name field* [body])`, heads and
  fields from the registry. The registry (registry/mettadinc_registry.json, declarations.Map) gives From and To the field
  type `expr`, so `(Map f (From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol)) (Cases ...))` is well formed. doc04
  uses this form in AnchorMigration and TaskResume.
- Spec 5.2 (l.1757-1758): every carrier states its element type, `(Carrier C (Of T) ...)`.
- Spec 5.3, admission obligations (l.1785): on an enumerated carrier, admission checks coverage of cases, absence
  of overlaps and that outputs stay in the carrier, by enumeration.
- Ben's reference evaluator (docs/e0/.../04_omega_memory_goals_part1/validation_bundle/mg_eval.py) treats a map
  as a function applied to values. It never reads From/To, and it compares observations and codes by equality.

Lowering (src/dcalc/model.c, `admit_typed_map` and `typed_map_on`; Crisp profile only):

- If From is a type T, the map is a function on values of T. It is tabulated on the carrier where it is used
  (the machine's states for Observe, Action and Encode, the Source machine's states for an AbstractionMap), and
  that carrier must declare `(Of T)`. Coverage and overlaps are checked on that carrier. This is the 5.3 obligation,
  and it is how the merged Subset lowering already treats a predicate `(From T)`.
- If From is a carrier P and To is a type, the map is tabulated on P at its declaration, and on a Subset or Reach
  carrier of P where it is used.
- If To is a type U, every value must have type U. Where the value must be a state (an Action or an
  AbstractionMap), the state carrier must declare `(Of U)`, and every value must be one of its elements;
  otherwise the answer is InvalidInput (the update leaves the carrier). Elsewhere (Observe, Encode), values go
  into an image carrier named by the printed type, e.g. `(Tuple Symbol Symbol)`, which is shared by all maps
  into U. That name is what a result's `(Target ...)` shows for a type-form code.
- Supported type forms: `(Tuple T ...)`, where each T is Symbol, Bool, Nat, Int or a nested Tuple. A Tuple with
  no components or a non-symbol head is malformed (InvalidInput). Any other type (for example `(Law Bit)`,
  `(Tuple A A)` over carrier names), a Body map, or a Cases operator outside Tuple/Add/Mul answers Unsupported,
  and the request's reason names the form.
- Not changed: a bare builtin name (`(To Bool)`, `(From Symbol)`) still takes the old path. `(To Bool)` as an
  Observe map is blocker (a), a separate task.

## Gate fixtures and hand-worked answers

Every type-form module TFn has a twin TFnC written with carrier names only. The gate requires TFn and TFnC to
give byte-identical answers after the module name, digest and `(Target ...)` are masked. It also requires each
status and witness to equal what Ben's evaluator gives (`reference_answers.py`, which uses mg_eval.World and
models/dclib's check_now, check_updates and check_abstraction_map, the same code mg_oracle.py uses for doc04).

| request | answer | hand derivation |
|---|---|---|
| TF1 (CheckNow R) | Refuted, (Pair (Tuple p r) (Tuple q r)), Observe fst | States AB = {p,q}x{r,s} in order (p r),(p s),(q r),(q s). keep2 sends (a b) to (b b), so the codes are (r r),(s s),(r r),(s s). The first pair with equal codes is (p r),(q r), and fst gives p and q there. |
| TF1 (CheckNow RI) | Checked | id is injective. |
| TF2 (CheckNow R) | Checked | code1 = (Tuple a) determines fst = a. |
| TF2 (CheckUpdates R) | Refuted, (Pair (Tuple p p) (Tuple p q)), Action swap | (p p) and (p q) both have code (p). swap gives (p p), code (p), and (q p), code (q). |
| TF3 (CheckAbstractionMap NaiveMigration) | Refuted at (Tuple absent none), Action repair | OldState = {(present old),(absent none)}, NewState = {(present new),(present old),(absent none)}. At (absent none): repair-old gives (present old), and rename sends that to (present new). rename gives (absent none), and repair-naive sends that to (present old). These differ. The first state, (present old), commutes. doc04 l.1422 answers Refuted. |
| TF3 (CheckAbstractionMap CellMigration) | Checked | repair-cell (absent none) = (present new) = rename(repair-old(absent none)). (present old) maps to (present new), which every action fixes as in the source; live agrees (yes/yes, no/no). doc04 l.1425 answers Checked. |
| TF4 (CheckNow NoRes) | Checked | The checkpoint (v f) carries flag f. |
| TF4 (CheckUpdates NoRes) | Refuted, (Pair (Tuple valid none current) (Tuple valid r1 current)), Action withdraw | Live = Reach from (valid none current) = {(valid none current),(valid r1 current),(withdrawn none current),(withdrawn r1 stale)}. The first two share the code (valid current). derive sends both to (valid r1 current). withdraw sends them to (withdrawn none current), code (withdrawn current), and to (withdrawn r1 stale), code (withdrawn stale). This is doc04 s7.3's NoReadSets pattern. |
| TF4 (CheckUpdates WithRes) | Checked | The code is injective. |

TF3 is doc04 s6.4 AnchorMigration with the other blockers written out. The Bool live-old and live-new
observations become an Enum carrier Live = {yes, no} (blocker a). If/Eq/And/Or/Not become literal Cases rows
(blocker c). The lesion Body map becomes a Cases map. The type-form maps `(From (Tuple Symbol Symbol))` are kept.
It reproduces doc04's two answers. TF4 has the shape of TaskResume: type-form To on the checkpoint maps, over a Reach
carrier. Its Resume machine repeats the ports instead of using `Like` (blocker d).

Negative cases (`fixtures/typeform_negative.metta`). Each answers InvalidInput, and the reason is checked:
NA From type versus the carrier's element type; NB a value not of the To type; NC an Action leaves the state
carrier; ND a malformed `(Tuple)`; NE a pattern no value of the From type can match; NF not total on the use
carrier; NG an Action's To type is not the states' type; NH overlapping Cases rows.

Unsupported cases (`fixtures/typeform_unsupported.metta`). The reason names the form: UA `(To (Law Bit))`;
UB If/Eq in a type-form Cases (blocker c); UC a Body type-form map (Checked since t-2026-11-24-mettadinc-m0-body-maps lowered
Body maps; the gate now checks that answer); UD `(Tuple A A)` over carrier names; UE an
AbstractionMap whose Source machine is outside the fragment, with the reason passed down from the map.

## Limits

- Coverage is checked on the carrier where the map is used, not on the whole type. A type-form map with no row
  for some value of T that no use carrier contains is admitted. This follows spec 5.3 and the existing Subset
  lowering. A totality check over a type such as `(Tuple Symbol Symbol)` would need a check of pattern
  exhaustiveness over an infinite type, and the spec does not ask for one.
- A type-form map that is declared but never used is checked only for its shape (well-formed type, rows are
  pairs, patterns fit the From type, operators inside the fragment).
- Only the Crisp profile is lowered; type-form maps in a Graded module keep their old answers.
