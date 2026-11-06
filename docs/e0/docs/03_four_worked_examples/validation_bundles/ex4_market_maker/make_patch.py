"""Writes ex4_registry_patch.json: the registry additions Example 4 proposes."""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.environ.get("MDINC_PACKAGE", os.path.join(HERE, "..", "..", "package"))
BASE = json.load(open(os.path.join(PKG, "registry", "mettadinc_registry.json")))
CARRIERS = ["Enumerated", "Symbolic", "Snapshot"]


def req(library, positional, args, result, statuses, claim, carriers=CARRIERS):
    return {"library": library, "positional": positional, "args": args, "result": result,
            "statuses": statuses, "profiles": ["Stochastic"], "carriers": carriers,
            "first_release": [], "claim": claim}


patch = {
    "patch": "Proposed registry additions used by Example 4 (market making across regime shifts)",
    "date": "2026-11-04",
    "libraries": {
        "Laws": {
            "primitives": ["Indep", "Image", "Expect", "LawOf"],
            "constants": [],
            "binders": ["Image"],
            "doc": ("finite rational laws as values: (Indep L1 ... Lk) is the product law, whose values are "
                    "k-tuples; (Image $v expr L) is the law of expr when $v is drawn from L, masses of equal "
                    "values added; (Expect L) is the mean of a rational-valued law; (LawOf m) is the law of a "
                    "declared Measure.  Coin and Point remain the elementary laws.  Laws are evaluated on "
                    "their support, so a value of mass zero is never produced and carrier closure is "
                    "checked on supports.")},
        "Monitors": {
            "primitives": ["Columns", "context", "observation", "each"],
            "constants": ["Union", "Mixture"],
            "doc": ("likelihood-ratio monitors for streams: a Monitor multiplies Alternative(c)(o) / Null(c)(o) "
                    "over the observations o of a Stream, each read in the context c posted before it.  "
                    "Exact claims about a monitor are Checked; detections on data are Estimated.")}},
    "declarations": {
        "DecisionProcess": {
            "library": "Decisions",
            "positional": [["name", "name"]],
            "fields": {
                "States": {"type": "ref:Carrier", "required": True},
                "Actions": {"type": "ref:Carrier", "required": True},
                "Kernel": {"type": "expr", "required": True,
                           "doc": "a map, or an instance of a parameterized map, from (Product States Actions) to (Law States)"},
                "RewardLaw": {"type": "expr", "required": True,
                              "doc": "a map or map instance from (Product States Actions) to (Law Rational)"},
                "Discount": {"type": "discount", "required": True},
                "Values": {"type": "ref:Tolerance", "required": False,
                           "doc": "value tolerance of the reward queries of the machine view"}},
            "body": None,
            "declares": "Machine",
            "doc": ("a finite discounted decision process.  It is also a stochastic Machine whose observations "
                    "are the expected rewards of its actions, one query (reward a) per action in declaration "
                    "order, so InduceExact, CheckUpdates, MeasureBehavioral and CheckAbstractionMap apply to it "
                    "unchanged; a quotient in that sense is an MDP homomorphism.")},
        "Monitor": {
            "library": "Monitors",
            "positional": [["name", "name"]],
            "fields": {
                "Context": {"type": "ref:Carrier", "required": True,
                            "doc": "what is fixed before each observation, such as the posted quote"},
                "Null": {"type": "expr", "required": True,
                         "doc": "map or map instance from Context to the law of one observation"},
                "Alternative": {"type": "expr", "required": True},
                "Columns": {"type": "expr", "required": True,
                            "doc": "(Columns [(context col+)] (observation col+)); (each col) reads every element of a list column as one observation"}},
            "body": None, "declares": "Monitor", "doc": ""},
        "Stream": {
            "library": "Monitors",
            "positional": [["name", "name"]],
            "fields": {
                "Source": {"type": "expr", "required": True, "doc": "a frozen data file"},
                "Digest": {"type": "expr", "required": True},
                "Provenance": {"type": "expr", "required": False}},
            "body": None, "declares": "Stream",
            "doc": "frozen observation data with provenance; a different digest is a different stream"}},
    "requests": {
        "AverageModel": req(
            "Decisions", [["model", "ref:DecisionModel|DecisionProcess"]],
            {"Under": {"type": "ref:Measure", "required": True},
             "Through": {"type": "ref:Representation", "required": False}},
            "AveragedModel", ["Checked"],
            ("prior-averaged reward law per action.  For a DecisionProcess with Through: the process on the "
             "codes whose rewards and pushed rows are averaged over each fiber under Under; admitted only when "
             "the hidden part is fresh (redrawn from Under at every step, independently of the rest), and then "
             "exact for every policy, history-dependent or not, that sees only the codes; InvalidInput otherwise")),
        "CheckEqual": req(
            "Decisions", [["left", "expr"], ["right", "expr"]],
            {"Compare": {"type": "enum:Laws|Means", "required": False, "default": "Laws",
                         "doc": "Laws compares reward laws; Means compares expected rewards, which is what "
                                "values and decisions of a risk-neutral process depend on"}},
            "Verdict", ["Checked", "Refuted"],
            ("the two averaged reward laws are equal; for decision processes on the same states and actions "
             "(declared or averaged), equal kernels and equal reward laws (Compare Laws) or equal expected "
             "rewards (Compare Means), with witness the least state, the first action and the first successor "
             "or reward value, in increasing order, whose masses differ")),
        "OptimizePolicy": req(
            "Decisions", [["model", "ref:DecisionModel|DecisionProcess"]],
            {"Through": {"type": "ref:Representation", "required": False},
             "Under": {"type": "ref:Measure", "required": True}},
            "PolicyValue", ["Checked"],
            ("optimal expected reward over policies that see only the representation.  For a DecisionProcess: "
             "the optimal discounted value from the start law Under, over stationary deterministic policies on "
             "states (no Through) or on codes (Through), evaluated in the concrete process, with the policy "
             "table and a Bellman certificate; on codes the class is memoryless code policies, which is every "
             "coarse policy when the hidden part is fresh")),
        "EvaluatePolicy": req(
            "Decisions", [["model", "ref:DecisionModel|DecisionProcess"]],
            {"With": {"type": "ref:ObservationMethod", "required": False},
             "Policy": {"type": "ref:Map", "required": False},
             "Through": {"type": "ref:Representation", "required": False},
             "Under": {"type": "ref:Measure", "required": True}},
            "PolicyValue", ["Checked"],
            ("exactly one of With and Policy.  With: expected reward of the best policy using the observation "
             "method, net of its cost; for a DecisionProcess the method reads the state component whose "
             "carrier is its channel's input once per step before the action, the policy also sees the code "
             "of Through, and values are computed on the hidden states, never by substituting the reading for "
             "the state.  Policy: the exact discounted value of the declared stationary policy from Under")),
        "CheckOptimal": req(
            "Decisions", [["process", "ref:DecisionProcess"]],
            {"Policy": {"type": "ref:Map", "required": True}},
            "OptimalityVerdict", ["Checked", "Refuted"],
            ("the stationary policy is optimal: its exact values V satisfy Q(x, pi x) >= Q(x, a) for every "
             "state and action, Q(x, a) = r(x, a) + gamma E V; Refuted with the least state, the policy's "
             "action, the first action in declaration order with a larger Q-value and the two exact Q-values")),
        "PullbackPolicy": req(
            "Decisions", [["arrow", "ref:AbstractionMap|CheckedAbstractionMap"]],
            {"Policy": {"type": "ref:Map", "required": True}},
            "PulledBackPolicy", ["Checked", "Refuted"],
            ("the arrow h is a homomorphism of decision processes (expected rewards and pushed rows preserved) "
             "and the policy x -> pi(h x) has at every source state the value pi has at h x; when h is "
             "surjective and pi is optimal for the target, the pulled-back policy is optimal for the source; "
             "Refuted with the homomorphism witness otherwise")),
        "CheckMonitor": req(
            "Monitors", [["monitor", "ref:Monitor"]], {},
            "MonitorCheck", ["Checked"],
            ("for every context the null expectation of the likelihood-ratio factor is at most one (exactly one "
             "when the alternative is absolutely continuous with respect to the null), so the product is a "
             "nonnegative supermartingale under the null for every policy that fixes the context before the "
             "observation; Blind when the two laws agree in every context; exact chi-square per context")),
        "Detect": req(
            "Monitors", [["monitors", "ref:Monitor", "variadic"]],
            {"On": {"type": "ref:Stream", "required": True},
             "Level": {"type": "rat01", "required": True},
             "Combine": {"type": "enum:Union|Mixture", "required": False, "default": "Union"}},
            "Detection", ["Estimated"],
            ("Estimated: if the stream follows the null laws, the probability that a listed monitor ever "
             "reaches its threshold is at most Level (Ville's inequality; Union gives each of k monitors the "
             "threshold k/Level, Mixture thresholds the average of the e-values at 1/Level); the result names "
             "the first monitor and observation to reach its threshold, or reports that none did, with the "
             "stream digest, the protocol and the dependence assumptions"),
            carriers=["Enumerated", "Snapshot"])},
    "result_types": {
        "OptimalityVerdict": {"fields": {"Values": "Table", "QValues": "Table", "Witness": "Witness?",
                                         "Certificate": "Certificate"},
                              "doc": "the exact values of the policy and the Q-table that certifies or refutes optimality"},
        "PulledBackPolicy": {"fields": {"Policy": "Map", "Values": "Table", "Certificate": "Certificate"},
                             "doc": ""},
        "MonitorCheck": {"fields": {"Valid": "Bool", "Blind": "Bool", "ChiSquare": "Table",
                                    "Certificate": "Certificate"}, "doc": ""},
        "Detection": {"fields": {"Fired": "Monitor?", "Step": "Nat?", "Observations": "Nat",
                                 "EValue": "Rational", "Threshold": "Rational", "Estimand": "Expr",
                                 "Procedure": "Expr", "Assumptions": "Expr"},
                      "doc": "an Estimated result: the claim is about the data source, never about the model"}},
    "result_fields": {
        "AveragedModel": {"Process": "DecisionProcess?"},
        "PolicyValue": {"Values": "Table?", "Certificate": "Certificate"}},
}

with open(os.path.join(HERE, "ex4_registry_patch.json"), "w") as f:
    json.dump(patch, f, indent=1)
    f.write("\n")
print("wrote ex4_registry_patch.json")
