# m0_gap_g: (To Bool) Observe maps declared with a type-form From (repro g)

Task t-2026-11-24-mettadinc-m0-gap-g. Base: mettadinc main 61eb9ba (merge of PR #51, the cases-logic rebase; contains
the bool-observe, typeform-maps, like-machines and body-maps lowerings). Gap (g) was found by
t-2026-11-23-mettadinc-m0-cases-logic: doc04 AnchorMigration declares its Bool Observe maps live-old/live-new as
`(Map live-old (From (Tuple Symbol Symbol)) (To Bool) (Cases ...))`. Neither existing lowering took that form: the
Bool Observe lowering (a) wanted From to name a declared carrier, the type-form lowering (b) wanted To to be a declared
carrier or a type form, not the builtin Bool. Probe: `tests/dcalc/examples_e2e/repro/m0_blocker_g_bool_typeform_from.metta`
(G1; control G1C, the same map with From AA).

    python3 tests/dcalc/m0_gap_g/run_m0_gap_g.py      # release and --beyond-release; 135 gates

## Meaning

The form combines the two lowerings, and nothing else is new:

- From a type form: as for every type-form map (spec 5.1 types; t-2026-11-23-mettadinc-m0-typeform-maps), the map is
  shape-checked once (`admit_typed_map`: pattern shapes, operator fragment) and tabulated on the carrier where it is
  used, here the states of the machine whose Observe port names it (`typed_map_on`, `dom` = the machine's states). The
  From type must be the element type of those states; the Cases must be total and non-overlapping on them (spec 5.4).
  A second machine using the same map gets its own tabulation on its own states (AnchorMigration: live-new on
  AfterNaive and AfterCell).
- To Bool: as for every (To Bool) Observe map (spec Def 3.1/3.2, Core builtin Bool; t-2026-11-23-mettadinc-m0-bool-observe),
  the query o_j = f has value type Y_j = Bool = {False, True} under literal equality, using the implicit Bool carrier;
  a value other than True or False is InvalidInput.
- Ben's reference evaluator reads the module the same way: `mg_eval.World` applies the map to each state value and
  ignores From/To (see ../m0_typeform_maps/reference_answers.py).

Lowering (src/dcalc/model.c): `admit_bool_observe_map` takes a `dom` argument; when the declaration has a type-form
From, `admit_map` (with `allow_bool`) routes it to `admit_typed_map`, and the map is then tabulated by
`typed_map_on(m, name, dom, -1, ...)`, whose To resolves to `bool_carrier(m)` when To is `Bool` and no Bool carrier is
declared. If tabulation fails, the map is unregistered as a type-form map and stays skipped, and the error is the answer.
Only Crisp modules and only Observe ports take this path (allow_bool is set only there).

## The gate (`run_m0_gap_g.py`, both modes)

Expected answers come from (1) hand derivations below, (2) Ben's reference evaluator (docs/e0 doc04 bundle, mg_eval +
models/dclib) on the same fixture text, (3) a twin GGnC of every module whose Bool maps name the declared state carrier
in From, which must answer byte-for-byte the same (module and digest masked), and (4) doc04's own answers.

- Probe: G1 (CheckNow R) -> Checked, four singleton blocks (Encode id is injective), byte-for-byte as G1C; G1C unchanged.
- `fixtures/gapg_gates.metta` (AA = {p,q}^2 in order pp pq qp qq):

| request | answer | derivation |
|---|---|---|
| GG1 (CheckNow RF) | Refuted (Pair pp pq), Observe same | same = Eq a b: T F F T. fst codes p p q q; pp, pq share p, same differs. |
| GG1 (CheckUpdates RF) | Refuted (Pair pp pq), Action swap | swap: pp -> pp (code p), pq -> qp (code q). |
| GG1 (CheckNow/CheckUpdates RE) | Checked, Blocks {pp qq} {pq qp} | eqc = If (Eq a b) y n is same renamed; swap preserves Eq. |
| GG1 (CheckNow RI) | Checked, four singletons | identity code. |
| GG2 (CheckNow R1) | Refuted (Pair pq qp), Observe live | States S = Subset AA (Not (Eq a b)) = {pq, qp}. pfirst has cases only for pq (True) and qp (False): it is total only on S, so it must be tabulated on S, not on AA. Constant code p. |
| GG2 (CheckUpdates R1) | Checked, one block | constant code before and after. |
| GG2 (CheckAbstractionMap H12) | Checked | h = flip-s, M1 -> M2. psecond = Eq b p: pq F, qp T, so psecond(flip s) = pfirst(s); flip commutes with flip. |
| GG2 (CheckAbstractionMap H13) | Refuted (State pq) (Observe live) | pq = Eq a p equals pfirst, so pq(flip pq) = F differs from pfirst(pq) = T. |
| GG2 (CheckAbstractionMap H12I) | Refuted (State pq) (Observe live) | h = id-s: psecond(pq) = F, pfirst(pq) = T. |
| GG2 (CheckAbstractionMap H13I) | Checked | h = id-s; pq = pfirst. |
| GG3 (CheckNow/CheckUpdates R) | Checked, one block | yes = (Body ($x) True) with a type-form From; constant code. |

- doc04 AnchorMigration, `memory_goals.metta` verbatim (docs/e0 04 bundle): NaiveMigration Refuted with
  `(CommutationWitness (State (Tuple absent none)) (Action repair) (Left (Tuple present new)) (Right (Tuple present old)))`
  (doc04 s6.4 l.1422; the reference evaluator and mg_results.json give the same state and action), CellMigration Checked
  (l.1425). The gate also checks that doc04 declares live-old/live-new in exactly this form.
- `fixtures/gapg_negative.metta`, near misses of G1, each in one respect; each must give the stated answer and the same
  status as its declared-carrier twin (From (Tuple Symbol Symbol) replaced by From AA):

| module | what differs | answer |
|---|---|---|
| NT1 | (To Truth), an undeclared name, not Bool | InvalidInput, undeclared name Truth (front end; unchanged from 61eb9ba) |
| NF1 | (From BB), an undeclared name, not a type form | InvalidInput, undeclared name BB (front end; unchanged) |
| NF2 | From (Tuple Symbol Symbol Symbol), not the states' element type | InvalidInput, "From type ... is not the element type of carrier AA" |
| NW1 | a value p, not True/False | InvalidInput, "sends (Tuple p p) to p, which leaves carrier Bool" |
| NW2 | no case for (q q) | InvalidInput, "not total on carrier AA; no value for (Tuple q q)" |
| NW3 | two cases match (p p) | InvalidInput, overlapping cases |
| NG1 | Profile Graded | Unsupported, "lowered only in a Crisp module" (unchanged) |
| NA1 | used as an Action | Unsupported (unchanged) |
| NE1 | also the Encode map | Unsupported, "Encode map live targets Bool; ... lowered only as an Observe port" |
| NU1 | (Body ($x) (Eq ...)) | Unsupported, "Body uses Eq, an operator outside the M0 fragment" (Body maps keep Tuple/Add/Mul) |
| NU2 | Xor in a Cases body (Crisp) | Unsupported, "Cases row 0 uses an operator outside the M0 fragment" |

On 61eb9ba NF2, NW1-3, NE1, NU1 and NU2 answered Unsupported "Map live: field From" (the form was not taken at all); they
now answer what their declared-carrier twins answer.

The gate fails on the 61eb9ba binary (106 of 135) and on two wrong-meaning mutants of the change that still answer
Checked/Refuted: every state gets the first state's value (24 failures) and state i gets the value of state n-1-i (12
failures). See evidence/m0-gap-g/.

## Limits

- The doc04 AnchorMigration answers alone do not tell these two mutants from the correct lowering (both mutants keep
  rows 43-44 as Refuted/Checked with the same witness); the GG fixtures do. The gate relies on them for meaning.
- A (To Bool) map with a type-form From is lowered only as an Observe port of a Crisp machine. As Encode, Action,
  Subset predicate or in another profile it keeps its old answer (Subset predicates with a type-form From were not
  examined here).
- Table bodies with a type-form From follow whatever `admit_typed_map` accepts; they are not gated here.
