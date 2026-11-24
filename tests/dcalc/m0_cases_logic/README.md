# m0_cases_logic: If/Eq/And/Or/Not inside Cases bodies (probe P3)

Task t-2026-11-23-mettadinc-m0-cases-logic. Base: mettadinc main fc6bffe (merge of PR #46; contains m0-subset-reach 8ae0fa7,
the bool-observe and type-form rebases).

    python3 tests/dcalc/m0_cases_logic/run_m0_cases_logic.py      # release and --beyond-release; 167 gates
    python3 tests/dcalc/m0_cases_logic/make_doc04_logic.py        # regenerates fixtures/doc04_logic.metta from doc04

## What the spec says, and the lowering

- Spec 5.1 grammar (mettadinc_language_spec.txt l.1721): `map-body ::= (Cases (pattern expr)+) | ...`, so a Cases row's
  right-hand side is any expression.
- Spec 5.4 (l.1858): "Admitted expressions are literals, constructors, field access, typed map application and registered
  pure primitives, each total on its declared input type". The registry (registry/mettadinc_registry.json,
  libraries.Core.primitives) lists Eq, If, Not, And and Or; Bool is a Core builtin type and True/False are Core constants.
- The spec text gives no evaluation rules for these primitives. Their meaning is taken from Ben's reference evaluators,
  which agree: docs/e0 doc04 mg_eval.py `World.ev` (`If`: `E(x[2]) if E(x[1]) else E(x[3])`; `Eq`: `==`; `And`/`Or`:
  `all`/`any` over the operands; `Not`: `not`), and the same in ls_eval.py and ex1 metta_eval.py ("If evaluates only the
  branch it takes").

Lowering (src/dcalc/model.c, `eval_logic`, called from `eval_body`; Crisp profile only):

| form | value |
|---|---|
| `(Eq a b)` | True iff a and b are the same value: literal equality of the evaluated operands, integer literals compared by value at every depth (so `(Tuple 1)` equals `(Tuple 01)`, as in the reference) |
| `(If c a b)` | the value of a if c is True, of b if c is False; only the chosen branch is evaluated |
| `(Not c)` | the complement of c |
| `(And c1 ... cn)`, n >= 2 | True iff every ci is True |
| `(Or c1 ... cn)`, n >= 2 | True iff some ci is True |

The forms nest freely with Tuple, Add and Mul, in every place a Crisp Cases body is tabulated: plain maps (`admit_map`),
type-form maps (`typed_map_on`, and the static operator check `body_in_fragment`), Subset predicates (`admit_subset`)
and (To Bool) Observe maps (through `admit_map`).

- **InvalidInput** (malformed; the reason names the form and the input): an If condition, or an operand of Not/And/Or, that
  is not True or False (spec 5.4: primitives are total on their declared input type, Bool here); If/Eq/Not with the wrong
  number of arguments; and, as before, a value outside the To carrier (e.g. a Bool where the carrier has no True/False).
- **Unsupported** (outside the fragment; the reason names the form): And/Or with fewer than two operands (the spec does not
  fix their arity; the reference evaluator would take them, so they are not called malformed); a Const name read by one of
  these forms, directly or nested anywhere in an operand it evaluates (inside a Tuple, Add or Mul; review 1 F1) (the
  lowering does not resolve Const names: the reference evaluator does, so reading the name literally would give a wrong
  answer; a nested logic form checks its own operands when it is evaluated, so a Const in an If branch that is not taken
  is not read); these forms in a non-Crisp module (Graded).

## Gates and how each expected answer is justified

1. **Probe P3** (examples_e2e/repro/m0_blocker_c_if_eq_cases.metta). ob(p) = If (Eq p p) p q = p, ob(q) = q, so ob is
   the identity and C1 is its literal-Cases control C1C: Checked, byte-identical to C1C with module and digest masked.
2. **logic_gates.metta**: six modules LG1-LG6, each with a twin LGnC whose maps are the same functions as literal Cases
   rows. Each answer must equal (a) the twin's, byte for byte after masking, and (b) Ben's reference evaluator (mg_eval.World
   + models/dclib check_now/check_updates/check_abstraction_map, via ../m0_typeform_maps/reference_answers.py): status and
   witness. Hand derivations:

| request | answer | derivation |
|---|---|---|
| LG1 (CheckNow R) | Refuted (Pair a c), Observe isa | code = If (Or (Eq s a) (Eq s c)) yes no: a yes, b no, c yes. isa: a yes, c no. |
| LG1 (CheckUpdates R) | Refuted (Pair a c), Action step | step = a->b, b->c, c->a (nested If). Codes of step a = b: no, step c = a: yes. |
| LG1 (CheckNow RI) | Checked | step is injective. |
| LG2 (CheckNow R) | Refuted (Pair (p p q) (q q p)), Observe maj | St = XXX minus (p p p) (Subset predicate Not (And ...) with three operands). code = (Eq x y, Eq y z): (p p q) and (q q p) both (True False); maj (three-way Or of Ands) is True on (p p q), False on (q q p). |
| LG2 (CheckUpdates R) | Refuted, same pair, Action setq | setq gives (q p q), code (False False), and (q q p), code (True False). |
| LG2 (CheckNow R3) | Checked | code3 = (maj, x) contains maj. |
| LG2 (CheckUpdates R3) | Refuted (Pair (p p q) (p q p)), Action rot | both code (True p); rot gives (p q p), code (True p), and (q p p), code (True q). |
| LG2 RI | Checked, Checked | identity code. |
| LG3 (CheckNow R) | Refuted (Pair 0 2), Observe zero | par = If (Or (Eq n 0) (Eq n 2)) 0 1 gives 0 on 0 and 2; zero gives 1 and 0. |
| LG3 (CheckUpdates R) | Checked | step = If (Eq n 3) 0 (Add n 1): classes {0,2} -> {1,3} and {1,3} -> {2,0}. |
| LG3 (CheckNow RI) | Checked | idn = If (Eq n 3) 3 n is the identity. |
| LG4 (CheckAbstractionMap H) | Refuted at (Tuple q p), Observe id | pick (q p) = (p q) (Eq q p is False, so the else branch swaps) but T observes (q p). (p p), (p q) commute. |
| LG5 (CheckNow R1) | Refuted (Pair q s), Observe live | live = Eq a q as a Bool Observe port: q True, s False; both code k2. |
| LG6 (CheckNow R) | Checked | identity code. |
| LG6 (CheckUpdates RF) | Refuted (Pair (q p) (q q)), Action pick | code fst = (q) for both; pick (q p) = (p q), code (p); pick (q q) = (q q), code (q). |
| LG7 (CheckNow R) | Refuted (Pair 0 1), Observe ob | ob = If (Eq (Tuple n) (Tuple 01)) yes no: 01 is the integer 1 inside the Tuple too (review 1 F2), so ob is no, yes, no; code e merges 0 and 1. A literal comparison would make ob constant and answer Checked. |

   LG4, LG5 and LG6 are the modules that typeform_unsupported UE, bool_observe_gates BU2 and typeform_unsupported UB used to
   show this gap as Unsupported. Those three fixtures now use Xor (outside the Crisp fragment unless the module is Neural)
   so that they still test an operator outside the fragment, and their If/Eq versions are gated here with their answers.
3. **doc04_logic.metta** (generated by make_doc04_logic.py from doc04's text): AnchorMigration and TaskResume with every
   If/Eq/And/Or/Not body verbatim. Only the forms of other gaps are rewritten, each by a single exact replacement: the
   Bool Observe maps live-old/live-new get From OldAll/NewAll instead of a type form (gap g), lesion and
   checkpoint-with-reads become Cases rows (gap f), and Resume gets Restart's ports instead of (Like Restart) (gap d). All
   seven doc04 answers come out: NaiveMigration Refuted (s6.4 l.1422), CellMigration Checked (l.1425), NoReadSets CheckNow
   Checked, CheckUpdates Refuted, CheckBehavioral Refuted, ReadSets CheckBehavioral Checked, ResumeMemory 11 classes on 12
   states (s7.3 l.1518-1524). The reference evaluator also gives the status and witness of the four requests it can run.
4. **logic_negative.metta**: NA-NI answer InvalidInput with the reason checked (non-Bool If condition, If with 2 arguments,
   Eq with 1, Not/And/Or of a non-Bool, a Bool value outside the To carrier, Not with 2 arguments in a type-form map, and a
   Subset predicate with a non-Bool If condition).
5. **logic_unsupported.metta**: UA unary And, UB nullary Or, UC Eq reading a Const, UD If/Eq in a Graded module answer
   Unsupported, the reason naming the form; UE (Sub in a taken If branch) is a control that stays Unsupported as before.
   UF, UG, UH (review 1 F1) read a Const nested in an operand: in a Tuple inside Eq in an Observe map (UF; read literally,
   result 1 answered Checked where the reference, resolving ka = a, answers Refuted (Pair a b) (Observe ob)), in a Tuple
   inside Not/Eq in a Subset predicate (UG; result 1 kept all four states where the spec meaning keeps three), and in an
   Add inside Eq (UH). Each answers Unsupported, the reason naming the form and the Const.

The gate (result 1 numbers; result 2 in evidence/m0-cases-logic/result2/README.md: 128, 40 and 26, and 10 on the result-1 binary) fails on the fc6bffe binary (118 failures) and on two wrong-meaning mutants that still answer Checked/Refuted:
If with its branches swapped (38 failures) and Or computed as And (26 failures). See evidence/m0-cases-logic/.

## Limits

- **Eq across types.** Eq compares values literally (integer literals by value). The Python reference compares Python
  values, where `1 == True`; a Cases body comparing a Nat with a Bool would differ. The spec types Eq's operands, so such a
  body is ill-typed; this lowering does not type-check Eq's operands and answers False.
- **Untaken branches.** If evaluates only its chosen branch, as the reference does. A malformed expression in a branch that
  no input reaches is not reported (on plain maps; type-form maps still check operators statically).
- **Unused maps.** A type-form map that is declared but never used is shape-checked only, as before; a malformed logic form
  in it is not reported.
- **Const names outside these forms.** A Const name in a Cases body that no If/Eq/And/Or/Not reads (e.g. a row giving
  `(Tuple $s ka)` directly) is still taken as the literal symbol, as at fc6bffe (pre-existing; the type-form probe T1
  shows it); only reads by the logic forms, where a literal reading changes a comparison, are refused here.
- **Not covered here**: Lt/Le, Sub/Div, typed map application and Const resolution in bodies stay outside the fragment;
  so do gaps (d), (f) and (g), which still block doc04 rows 43-49 (see examples_e2e/README.md finding 5).
