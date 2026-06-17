\# IIIS v4.6 AGENT GOVERNANCE FILE



\## READ FIRST



Before any action read:



docs/IIIS\_V4\_6\_FROZEN\_SPEC.md



This file is the authoritative source of truth.



The frozen specification overrides:



\* Existing code

\* Existing tests

\* Existing implementation

\* Existing documentation

\* Previous AI decisions

\* AGENT.md



If any conflict exists:



The frozen specification wins.



Never implement from memory.



Never implement from summaries.



Never implement from assumptions.



Always verify requirements directly from:



docs/IIIS\_V4\_6\_FROZEN\_SPEC.md



---



\# CURRENT PROJECT STATUS



This repository already contains partially completed implementation.



The implementation may contain architectural drift.



The implementation may contain incorrect assumptions.



The implementation may contain features that do not match specification.



Do not assume existing code is correct.



Do not assume passing tests mean specification compliance.



---



\# PRIMARY MISSION



Restore and maintain full compliance with IIIS v4.6 specification.



Before writing new code:



1\. Audit existing implementation.

2\. Compare implementation with specification.

3\. Detect mismatches.

4\. Create discrepancy report.

5\. Fix mismatches.

6\. Run tests.

7\. Confirm compliance.

8\. Continue development only after alignment.



---



\# RECOVERY MODE



Enter Recovery Mode immediately.



Do not begin new features until recovery is complete.



Recovery Mode Tasks:



1\. Scan repository.

2\. Identify completed phases.

3\. Compare completed phases with specification.

4\. Generate compliance report.

5\. Generate fix plan.

6\. Apply fixes.

7\. Re-run tests.

8\. Confirm alignment.



---



\# SPECIFICATION AUTHORITY



Priority Order:



1\. docs/IIIS\_V4\_6\_FROZEN\_SPEC.md

2\. Non-Negotiable Rules

3\. Database Schema

4\. AGENT.md

5\. Existing Code



Specification always wins.



Never modify specification to match code.



Modify code to match specification.



---



\# CRITICAL COMPLIANCE CHECKS



Verify all of the following:



\* System never executes trades

\* Human always makes final trade decision

\* ARC never runs in live scan

\* GEIE never blocks alerts

\* GEIE weight is zero

\* ARC weight is zero

\* Big Money weight is zero

\* Big Money only upgrades risk grade

\* Score threshold remains strictly above 85

\* Maximum four active alerts

\* Maximum two same-sector alerts in thirty minutes

\* Risk per trade remains 0.5%

\* Maximum daily risk remains 2%

\* Hard stop remains three consecutive losses

\* Ghost Mode requires manual resume

\* Audit log remains append-only

\* All eight gates run before AI layers

\* All sixteen database tables exist



Any violation must be reported and fixed.



---



\# DEVELOPMENT RULE



No new phase work until repository is aligned with specification.



No shortcuts.



No silent architecture changes.



No undocumented behavior.



No business-rule modifications without approval.



---



\# REQUIRED AUDIT OUTPUT



For every audit provide:



COMPLIANT ITEMS



NON-COMPLIANT ITEMS



FILES AFFECTED



RISK LEVEL



FIX PLAN



TESTS REQUIRED



FINAL STATUS



Development may continue only when:



FINAL STATUS = ALIGNED



