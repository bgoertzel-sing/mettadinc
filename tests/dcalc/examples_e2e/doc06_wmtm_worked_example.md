# Document 06: per-request CLI answers

| run | module | request | release | beyond | reason (beyond) | bundle expects |
|---|---|---|---|---|---|---|
| wx | WMTMStore | `(CheckStatistic EventStat (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMStore | `(CheckStatistic JointStat (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMStore | `(CheckStatistic NagIndex (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMStore | `(CheckNow WindowView)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMStore | `(CheckUpdates WindowView)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMStore | `(CheckStatistic Records (Method Lift))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMStore | `(CheckStatistic EngineIndex (Method Lift))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMStore | `(CheckStatistic NagIndexByKey (Method Lift))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic JointCarried (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckNow CarriedIndex)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic RecordS (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic JointS (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic NagTwoIndex (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckNow TwoForThree)` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic NagThreeIndex (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic RebuildFromRecords (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic RebuildEngineIndex (Method Symbolic))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic EngineIndexS (Method Lift))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMRelease | `(CheckStatistic NagIndexS (Method Lift))` | Unsupported | Unsupported | library RationalArith is outside the first release |  |
| wx | WMTMReceipts | `(CheckMonitor MissTenth)` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(CheckMonitor MissFifth)` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(CheckMonitor MissTwoFifths)` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(Detect MissTenth MissFifth MissTwoFifths (On Replies) (Level (Rat 1 100)) (Combine Mixture))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(Detect MissTenth MissFifth MissTwoFifths (On Replies) (Combine Mixture) (Scheme ShiryaevRoberts) (MeanTimeToFalseAlarm 100000))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(EstimateRate (On RepliesBefore) (Column "stale") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(EstimateRate (On AuditAfterAlarm) (Column "missed") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(EstimateRate (On AuditV2) (Column "missed") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(EstimateRate (On RepliesGate) (Column "stale") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(EstimateRate (On KeysGate) (Column "duplicate") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(EstimateRate (On ClosuresGate) (Column "spurious") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(CompareRates (On LivesGate) (First "window_bad") (Second "event_bad") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(EstimateRate (On AuditRepliesGate) (Column "missed") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |
| wx | WMTMReceipts | `(EstimateRate (On AuditOpenGate) (Column "false_close") (Equals 1) (Level (Rat 1 100)))` | Unsupported | Unsupported | library Laws is outside the first release |  |

## Totals (run, release, beyond): count

- wx Unsupported/Unsupported: 33
