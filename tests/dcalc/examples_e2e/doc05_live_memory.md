# Document 05: per-request CLI answers

| run | module | request | release | beyond | reason (beyond) | bundle expects |
|---|---|---|---|---|---|---|
| ls | LiveOpenItems | `(CheckStatistic EventStat (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveOpenItems | `(CheckStatistic JointStat (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveOpenItems | `(CheckStatistic EngineStat (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveOpenItems | `(CheckNow WindowView)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveOpenItems | `(CheckUpdates WindowView)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveOpenItems | `(CheckStatistic EventIndex (Method Lift))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveOpenItems | `(CheckStatistic JointIndex (Method Lift))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveOpenItems | `(CheckStatistic EngineIndex (Method Lift))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveOpenItems | `(CheckStatistic EngineAsItems (Method Lift))` | InvalidInput | InvalidInput | Keyed EngineAsItems: field Item: statistic EngineStat is of EngineTime, not of ItemTime (the Store's item machine); declare (View ...) | InvalidInput |
| ls | LiveEvidence | `(CheckStatistic FirstOrMore (Method Symbolic))` | Unsupported | Unsupported | library NatArith is outside the first release |  |
| ls | LiveGoals | `(CheckNow DaysLeft)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckNow NagForDays)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckNow BenFirst)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckNow NagForBenFirst)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckNow Cap3)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckNow NagForCap3)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckStatistic SaturateAtTwo (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckNow TwoForBoth)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckStatistic SaturateAtThree (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveGoals | `(CheckStatistic Deadline (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveArbitration | `(CheckSimulation StutterWeighted)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveArbitration | `(CheckSimulation StutterNormFirst)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveArbitration | `(CheckSafety NormFirst (Never (Shows unlawful True)) (Via StutterNormFirst) (Init live-start))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveArbitration | `(CheckSafety Weighted (Never (Shows unlawful True)) (Via StutterWeighted) (Init live-start))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveArbitration | `(CheckSafety NormFirst (Never (Shows unlawful True)) (Via StutterWeighted) (Init live-start))` | InvalidInput | InvalidInput | CheckSafety NormFirst: field Via: simulation StutterWeighted targets Weighted, not NormFirst | InvalidInput (fixture comment) |
| ls | LiveMotivation | `(CheckBlockPartition SafePlain (Of PlainWatch) (Budget (Unrollings 8)))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveMotivation | `(CheckBlockPartition SafeFloor (Of FloorWatch))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveMotivation | `(CheckImplementation OrderSwapGoals (Grade 1 (Rat 9 10)))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveMotivation | `(CheckImplementation OrderSwapGoals (Grade 1 (Rat 4 5)))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveMotivation | `(CheckImplementation OrderSwapSettled (Grade 1 0))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| ls | LiveReceipts | `(EstimateRate (On ContextReceipts) (Column "relevance_A") (Equals 0) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| ls | LiveReceipts | `(EstimateRate (On ContextReceipts) (Column "consumer_A") (Equals 0) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| ls | LiveReceipts | `(CompareRates (On ContextReceipts) (First "relevance_A") (Second "consumer_A") (Equals 0) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| ls | LiveReceipts | `(EstimateRate (On LiveSuggestions) (Column "stale") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| ls | LiveReceipts | `(CheckMonitor StaleFifth)` | Unsupported | Unsupported | library Laws is outside the first release |  |
| ls | LiveReceipts | `(Detect StaleFifth (On TenPercent) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| ls | LiveReceipts | `(Detect StaleTenth StaleFifth StaleTwoFifths (On TenPercent) (Level (Rat 1 100)) (Combine Mixture))` | Unsupported | Unsupported | library Laws is outside the first release |  |

## Totals (run, release, beyond): count

- ls InvalidInput/InvalidInput: 2
- ls Unsupported/Unsupported: 35
