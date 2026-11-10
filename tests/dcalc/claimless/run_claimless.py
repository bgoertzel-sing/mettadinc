#!/usr/bin/env python3
"""OQ3 (M2): small deterministic tests for requests that have no claim row
in the oracle (claimless heads). Each case runs dcalc on a module in this
directory and compares Status and the exact Value term with a hand-derived
expectation recorded below (derivations in the .metta comments)."""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DCALC = os.environ.get('DCALC', os.path.join(ROOT, 'build/dcalc/dcalc'))

CASES = {
 'graded_four.metta': {
  'GradedFour Closed': ('Checked', '(Value (Kernel (On Point) (Entries (Entry A A 1) (Entry A B 4/5) (Entry A C 1/2) (Entry A D 0) (Entry B A 4/5) (Entry B B 1) (Entry B C 7/10) (Entry B D 1/5) (Entry C A 1/2) (Entry C B 7/10) (Entry C C 1) (Entry C D 1/2) (Entry D A 0) (Entry D B 1/5) (Entry D C 1/2) (Entry D D 1))))'),
  'GradedFour Before': ('Checked', '(Value (Bracket (Mean 1/2) (Under UU) (Pairs 16)))'),
  'GradedFour After': ('Checked', '(Value (Bracket (Mean 47/80) (Under UU) (Pairs 16)))'),
  'GradedFour Increase': ('Checked', '(Value (Delta (From 1/2) (To 47/80) (Increase 7/80)))'),
  'GradedFour Thresholded': ('Checked', '(Value (Relation (On Point) (Pairs (Pair A A) (Pair A B) (Pair A C) (Pair B A) (Pair B B) (Pair B C) (Pair C A) (Pair C B) (Pair C C) (Pair C D) (Pair D C) (Pair D D))))'),
 },
 'weak_three.metta': {
  'WeakThree Split': ('Checked', '(Value (Refinement (Representation Split) (Partition (Block P) (Block Q) (Block R)) (Ledger (Under Uniform) (Before 1/3) (After 1/3))))'),
  'WeakThree Tight': ('Checked', '(Value (WeakestPartition (Representation Tight) (Partition (Block P Q) (Block R)) (Weakness 5/9) (Defect (Interval 1/10 1/10)) (Bound 1/10) (Kind Behavioral) (Under Uniform) (Optimality Checked)))'),
  'WeakThree Loose': ('Checked', '(Value (WeakestPartition (Representation Loose) (Partition (Block P Q R)) (Weakness 1) (Defect (Interval 3/10 3/10)) (Bound 3/10) (Kind Behavioral) (Under Uniform) (Optimality Checked)))'),
  'WeakThree TightMachine': ('Checked', '(Value (ApproximateAbstraction (Machine (Output TightMachine Machine)) (States 2) (Selector (Choose pick)) (Representatives (Class 0 (Block P Q) Q) (Class 1 (Block R) R)) (Radius 1/10) (Defect (Interval 1/10 1/10)) (Bound Unbounded) (AbstractionMap (Kind Graded) (Defect 1/10))))'),
  'WeakThree (MeasureUpdates Coarse)': ('Checked', '(Value (DefectMeasurement (Defect (Interval 0 0)) (Kind Update) (Equality Literal)))'),
  'WeakThree (MeasureNow Coarse)': ('Checked', '(Value (DefectMeasurement (Defect (Interval 1/5 1/5)) (Kind Current) (Equality Literal)))'),
 },
 'refine_three.metta': {
  'RefineThree Split': ('Checked', '(Value (Refinement (Representation Split) (Partition (Block P) (Block Q) (Block R)) (Ledger (Under Uniform) (Before 5/9) (After 1/3))))'),
 },
 'trace_four.metta': {
  'TraceFour (MeasureTrace Q (Horizon (Steps 1)))': ('Checked', '(Value (DefectMeasurement (Defect (Interval 0 0)) (Kind Trace) (Equality Literal)))'),
  'TraceFour (MeasureTrace Q (Horizon (Steps 2)))': ('Checked', '(Value (DefectMeasurement (Defect (Interval 1 1)) (Kind Trace) (Equality Literal)))'),
  'TraceFour (CheckTrace Q (Horizon (Steps 1)))': ('Checked', '(Value (DefectCheck (Defect (Interval 0 0)) (Bound 0) (Kind Trace) (Equality Literal)))'),
  'TraceFour (CheckTrace Q (Policies ObservationBased))': ('Refuted', '(Value (DefectCheck (Defect (Interval 1 1)) (Bound 0) (Kind Trace) (Equality Literal)))'),
 },
 'beh_four.metta': {
  'TraceFour (BehavioralTolerance M (Discount (Rat 1 2)))': ('Checked', '(Value (ToleranceResult (Tolerance (Kernel (On S) (Entries (Entry A A 1) (Entry A B 3/4) (Entry A C 1/2) (Entry A D 0) (Entry B A 3/4) (Entry B B 1) (Entry B C 1/2) (Entry B D 0) (Entry C A 1/2) (Entry C B 1/2) (Entry C C 1) (Entry C D 0) (Entry D A 0) (Entry D B 0) (Entry D C 0) (Entry D D 1)))) (Certificate (Kind TwoSided) (Lower (WordTests 6)) (Upper Prefixpoint))))'),
  'TraceFour (BehavioralTolerance M (Horizon (Steps 1)))': ('Checked', '(Value (ToleranceResult (Tolerance (Kernel (On S) (Entries (Entry A A 1) (Entry A B 1) (Entry A C 0) (Entry A D 0) (Entry B A 1) (Entry B B 1) (Entry B C 0) (Entry B D 0) (Entry C A 0) (Entry C B 0) (Entry C C 1) (Entry C D 0) (Entry D A 0) (Entry D B 0) (Entry D C 0) (Entry D D 1)))) (Certificate (Kind TwoSided) (Lower (WordTests 5)) (Upper LayeredPrefixpoint))))'),
  'TraceFour (BehavioralTolerance M)': ('Checked', '(Value (ToleranceResult (Tolerance (Kernel (On S) (Entries (Entry A A 1) (Entry A B 0) (Entry A C 0) (Entry A D 0) (Entry B A 0) (Entry B B 1) (Entry B C 0) (Entry B D 0) (Entry C A 0) (Entry C B 0) (Entry C C 1) (Entry C D 0) (Entry D A 0) (Entry D B 0) (Entry D C 0) (Entry D D 1)))) (Certificate (Kind TwoSided) (Lower (WordTests 6)) (Upper Prefixpoint))))'),
 },
 'min_pairs.metta': {
  'MinPairs (MinimizeForQueries M)': ('Checked', '(Value (Refinement (Representation ?) (Partition (Block A B) (Block C D) (Block E))))'),
 },
 'then_eight.metta': {
  'ThenEight SecondChecked': ('Checked', '(Value (CheckedAbstractionMap (Kind Quotient) (Surjective True)))'),
  'ThenEight Composed': ('Checked', '(Value (ComposedArrow (Source Concrete) (Target Codes) (Kind Quotient)))'),
 },
}

def term_at(s, i):
    d = 0
    for j in range(i, len(s)):
        if s[j] == '(': d += 1
        elif s[j] == ')':
            d -= 1
            if d == 0: return s[i:j+1]
    return None

def field(res, head):
    i = res.find('(' + head + ' ')
    return term_at(res, i) if i >= 0 else None

def main():
    fails = total = 0
    for fn, exp in CASES.items():
        out = subprocess.run([DCALC, os.path.join(HERE, fn)], capture_output=True, text=True, timeout=60).stdout
        got = {}
        for line in out.splitlines():
            if ' => ' in line:
                k, r = line.split(' => ', 1); got[k.strip()] = r
        for key, (st, val) in exp.items():
            total += 1
            r = got.get(key)
            if r is None:
                ok, why = False, 'no result line'
            else:
                gst = field(r, 'Status'); gval = field(r, 'Value')
                ok = gst == '(Status %s)' % st and gval == val
                why = '' if ok else 'status=%s value=%s' % (gst, (gval or '')[:160])
            fails += not ok
            print('%s %s: %s %s' % ('PASS' if ok else 'FAIL', fn, key, why))
    print('claimless: %d/%d PASS' % (total - fails, total))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
