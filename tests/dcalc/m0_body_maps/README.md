# m0_body_maps: (Body ($v) expr) maps in the Crisp M0 lowering (t-2026-11-24-mettadinc-m0-body-maps)

Gap (f) of t-2026-11-23-mettadinc-m0-bool-observe. Probe: `tests/dcalc/examples_e2e/repro/m0_blocker_f_crisp_body.metta`
(F1, a `(Map reset (From A) (To A) (Body ($x) p))` action; control F1C, the same map as Cases).

## What the form means, and where that is written

- Spec 5.1 grammar (txt l.1721): `map-body ::= (Cases (pattern expr)+) | (Body ($v) expr) | (Table (in out)+) | ...`.
- Spec 5.4 (l.1851-1856): every core map is unary; "Body binds its single argument lexically". So the map sends x to
  the value of expr with $v bound to x, and expr may use no other variable. This is the one-case map
  `(Cases ($v expr))`: a variable pattern matches every input exactly once.
- Spec 5.3 admission obligations (l.1784-1786): on an enumerated carrier, admission checks coverage, absence of overlaps
  and that outputs stay in the carrier, by enumeration. For a Body map, coverage is totality (expr has a value on every
  input) and there is nothing to overlap.
- Ben's reference evaluator reads it the same way: `mg_eval.py` `World.call` evaluates `(Body ($v) e)` as
  `ev(e, {$v: arg})`.

Lowering (`src/dcalc/model.c`: `body_var`, `body_check`, the Body branch of `admit_map`, and the Body case of
`admit_typed_map` / `typed_map_on`): in a Crisp module, expr is evaluated by `eval_body`, the evaluator of Cases
bodies, with $v bound to each element of the carrier the map is tabulated on, and the map becomes a table. That carrier
is the From carrier for a map between declared carriers (including a `(To Bool)` Observe map), and, for a map declared
with a type form, the carrier where it is used, exactly as for type-form Cases maps. Nothing else is new: everything
downstream sees an ordinary table.

- Unsupported, the reason naming the operator: expr uses an operator outside the Cases-body fragment
  (`body_in_fragment`: Tuple, Add, Mul; Xor in a Neural module), e.g. If, Eq, GetTuple, Sub. The outermost such
  operator is named. When the cases-logic lowering (If/Eq/And/Or/Not) is merged, Body bodies get those operators through
  the same `body_in_fragment`/`eval_body`; its `logic_on`/`logic_off` and `ok == 4` handling must then also wrap the
  two Body evaluations (see evidence/m0-body-maps/resolve_scratch_merge.py for a tested resolution).
- InvalidInput: a value outside To (a declared carrier, the Bool carrier, or the To type); no value on some input (not
  total; in this fragment, Add/Mul on a non-integer or an overflow); an action value outside the state carrier; an unbound
  variable; a malformed `(Body ...)` (not one `($v)` binder and one expr). The front end (admit.c) already refuses
  unbound variables.
- Body maps in other profiles keep their old behaviour (Graded FiniteSets and Contracts Body maps are lowered elsewhere;
  any other profile stays Unsupported).

## The gate (`run_m0_body_maps.py`, both modes)

Fixtures (`fixtures/`); every Body module has a written-out twin (suffix C, Table or literal Cases) that must answer
byte-for-byte the same, and every answer is also checked against the reference evaluator run on the same file.

- Probe: F1 CheckNow R -> Checked, Blocks (p) (q) (worked by hand: Observe and Encode are both id, so the code is
  injective and agrees with the observation; reset does not affect CheckNow), byte-for-byte as F1C; F1C unchanged.
- `body_gates.metta`, worked by hand:
  - BG1, Int arithmetic between declared carriers. X = {-2 -1 0 1 2}, neg x = -x, sq x = x*x, pron x = x*x + x
    (= 2 0 0 2 6), id. M observes sq and acts by neg; MI observes id.
    RSq (encode sq): codes equal the observation and neg preserves sq: CheckNow, CheckUpdates, CheckBehavioral Checked,
    blocks {-2 2} {-1 1} {0}. RQ (encode pron): -2 and 1 share code 2 but sq gives 4 vs 1: CheckNow Refuted, pair (-2 1);
    after neg they go to 2 and -1, codes 6 vs 0: CheckUpdates Refuted, pair (-2 1), action neg; CheckBehavioral Refuted,
    empty word. RI (MI, encode sq): -2 and 2 share code 4 but id differs: Refuted, pair (-2 2). MinimizeForQueries M:
    3 blocks {-2 2} {-1 1} {0}.
  - BT1, the doc04 shapes: type-form From/To, a constant Body (lesion = (Tuple absent none)), the identity (keep), a
    constant code (forget = (Tuple none)) and a type-form To on a declared From (wrap x = (Tuple x old)). keep, wrap:
    injective, Checked. forget: CheckNow Refuted, pair ((present old) (present none)), live old vs none; CheckUpdates
    Checked (all codes are equal before and after); CheckBehavioral Refuted, empty word.
  - BT2: BG1's RQ with tuple-valued codes and observations (type-form To on a declared From): the same witnesses,
    codes (Tuple 2). Unlike BT1, the values depend non-symmetrically on the input.
  - BB1: a Body map as a (To Bool) Observe port (constant True) and a constant Body encoding: Checked, one block (p q).
- doc04 with its Body maps verbatim and every other gap desugared:
  - TaskResume: module TRL of `tests/dcalc/m0_like/fixtures/taskresume_like.metta` with checkpoint-with-reads put back as
    doc04 writes it (`(To (Tuple Symbol Symbol Symbol Symbol)) (Body ($x) $x)`): doc04 s7.3's five answers (CheckNow
    NoReadSets Checked, CheckUpdates NoReadSets Refuted, CheckBehavioral NoReadSets Refuted, CheckBehavioral ReadSets
    Checked, ResumeMemory 11 classes on 12 states), witnesses and blocks as the reference evaluator on memory_goals.metta.
  - AnchorMigration: module AnchorMigrationD of `tests/dcalc/m0_bool_observe/fixtures/doc04_desugared.metta` with doc04's
    lesion (`(From (Tuple Symbol Symbol)) (To (Tuple Symbol Symbol)) (Body ($x) (Tuple absent none))`) in place of its
    two tabulated copies: NaiveMigration Refuted, CellMigration Checked (doc04 s6.4), byte-for-byte as AnchorMigrationD.
  - The gate also checks that memory_goals.metta still writes both maps in exactly these forms.
- `body_invalid.metta`, InvalidInput: BN1 a value outside To (inc 2 = 3 not in N); BN2 not total (Add overflows on the
  largest Int); BN3 a value outside the To type; BN4 not total on a type-form map (Add on a tuple); BN5 a type-form lesion
  that leaves a Subset state carrier; BN6 a (To Bool) Body giving p; BN7 an unbound variable; BN8, BN9 malformed binders.
- `body_unsupported.metta`, Unsupported naming the operator: BU1 If (doc04's form, gap c), BU2 GetTuple on a type-form
  map, BU3 Sub inside Add.

Evidence: `evidence/m0-body-maps/`.
