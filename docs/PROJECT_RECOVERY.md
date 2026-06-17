\# PROJECT RECOVERY MODE



Version: IIIS v4.6



Status: Mandatory



---



\## PURPOSE



This repository contains partially completed implementation.



The implementation may contain architectural drift.



The implementation may not fully comply with:



docs/IIIS\_V4\_6\_FROZEN\_SPEC.md



Before any new development begins the repository must be audited and aligned.



---



\## SOURCE OF TRUTH



The authoritative source is:



docs/IIIS\_V4\_6\_FROZEN\_SPEC.md



If code conflicts with specification:



Specification wins.



If tests conflict with specification:



Specification wins.



If documentation conflicts with specification:



Specification wins.



---



\## RECOVERY OBJECTIVES



The agent must:



1\. Audit all completed phases.

2\. Compare implementation against specification.

3\. Identify deviations.

4\. Generate compliance report.

5\. Generate fix plan.

6\. Apply fixes.

7\. Run tests.

8\. Confirm alignment.



No new features may be implemented until alignment is complete.



---



\## REQUIRED AUDIT AREAS



\### Architecture



Verify:



\* System never executes trades

\* Human remains final decision maker

\* Alert-only workflow



\### ARC



Verify:



\* Pre-market only

\* Post-market only

\* Never inside live scan



\### GEIE



Verify:



\* Uses cache

\* Never blocks alerts

\* Weight remains zero



\### Big Money



Verify:



\* Weight remains zero

\* Used only for grade upgrades

\* Never blocks signals



\### Composite Score



Verify:



Regime = 25%



RS = 20%



RVOL = 15%



Breadth = 10%



Options = 10%



Sector = 10%



SMC Quality = 10%



Total = 100%



\### Risk Gates



Verify all 8 gates.



Verify all gates execute before AI layers.



\### Database



Verify all 16 required tables exist.



\### Monitoring



Verify Ghost Mode behavior.



Verify manual resume requirement.



---



\## RECOVERY EXECUTION ORDER



Step 1:

Audit Repository



Step 2:

Generate Compliance Report



Step 3:

Generate Fix Plan



Step 4:

Implement Fixes



Step 5:

Update Tests



Step 6:

Run Full Test Suite



Step 7:

Generate Final Alignment Report



---



\## COMPLETION CRITERIA



Repository is aligned only when:



All tests pass.



All specification requirements pass.



No architectural drift remains.



Final Status = ALIGNED



Only after Final Status = ALIGNED may feature development continue.



