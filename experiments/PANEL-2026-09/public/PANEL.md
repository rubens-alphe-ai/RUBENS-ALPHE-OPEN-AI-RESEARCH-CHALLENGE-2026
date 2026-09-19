# Reader panel: answer from the note alone

Below is a handover note, then 37 questions about the project it describes.
You have not seen that project and you will not be shown it.

Answer every question with one letter. Where the note does not contain the
answer, the honest choice is the option that says so — it is a real option
on every question, and choosing it is never penalised. Guessing is.

Reply with 37 lines, one per question, like `Q01 B`. Use the identifier
printed with each question — they are not all numbered the same way, and the
last one is `X10`. Nothing else in the reply.

## The note

Meridian settles 84k transactions/day across 11 regions on 6 app nodes and 2 DB replicas. On-call rotates weekly (5 engineers), handover Monday 09:00 UTC. Use runbook 4.2 (12 March 2026); 3.9 is obsolete but still linked on the wiki.

Traffic averages 58 tps, peaking at 190 at month-end. Error budget: 0.15% quarterly, 0.09% used.

Key rules: no deploys 16:00 Friday–09:00 Monday; settlement-logic changes need a traffic replay; draining a region needs one engineer, restoring needs two; incident notes within 24 hours.

Watch: unvalidated circuit-breaker threshold (20), an unidentified second cause in the February config incident, and unmodelled month-end capacity after next quarter's onboarding.

## The questions

**Q01** On which day and time does the handover occur?
- A) Wednesday at 08:00 UTC
- B) Tuesday at 10:00 UTC
- C) Friday at 16:00 UTC
- D) Monday at 09:00 UTC
- E) The text does not say.

**Q02** When was runbook version 4.2 published?
- A) 12 February 2026
- B) 1 April 2026
- C) 15 March 2026
- D) 12 March 2026
- E) The text does not say.

**Q03** What is the quarterly error budget as a percent of requests?
- A) 0.05 percent
- B) 0.20 percent
- C) 0.10 percent
- D) 0.15 percent
- E) The text does not say.

**Q04** How long did the primary database run at 100% CPU during the January incident?
- A) 20 minutes
- B) 55 minutes
- C) 30 minutes
- D) 41 minutes
- E) The text does not say.

**Q05** After the February incident, what new requirement exists for config changes?
- A) require a second approver
- B) need a rollback plan
- C) must be documented in the wiki
- D) must be done at night
- E) The text does not say.

**Q06** Why was the TLS‑certificate alert not seen?
- A) The certificate was whitelisted
- B) The monitoring system was down
- C) It routed to a decommissioned channel
- D) The alert threshold was too high
- E) The text does not say.

**Q07** During which days are deployments prohibited?
- A) Between 00:00 UTC Sunday and 23:59 UTC Sunday
- B) Between 12:00 UTC Saturday and 12:00 UTC Sunday
- C) Between 08:00 UTC Monday and 18:00 UTC Friday
- D) Between 16:00 UTC Friday and 09:00 UTC Monday
- E) The text does not say.

**Q08** What must be done before merging any change to settlement logic?
- A) Obtain CEO approval
- B) Replay against the previous day's traffic
- C) Run a full regression suite
- D) Deploy to a staging environment
- E) The text does not say.

**Q09** Who can drain a region?
- A) The database admin
- B) A senior manager
- C) The on‑call engineer alone
- D) Any engineer
- E) The text does not say.

**Q10** What is required to restore a drained region?
- A) The same on‑call engineer
- B) An automated script
- C) A second engineer
- D) Approval from product
- E) The text does not say.

**Q11** Within how many hours must incident notes be written?
- A) 12 hours
- B) 72 hours
- C) 24 hours
- D) 48 hours
- E) The text does not say.

**Q12** To which component is the reconciliation job planned to be migrated?
- A) a serverless function
- B) the database layer
- C) the workflow engine
- D) a new microservice
- E) The text does not say.

**Q13** What is the planned addition to the database infrastructure?
- A) a backup replica in eu‑central
- B) a read‑only replica in ap‑south
- C) a third replica in the eu‑west region
- D) a fourth replica in the us‑east region
- E) The text does not say.

**Q14** What is the status of the third database replica addition?
- A) completed
- B) in progress
- C) approved but not started
- D) deferred
- E) The text does not say.

**Q15** What is the current status of retiring runbook 3.9?
- A) pending manager approval
- B) scheduled for next month
- C) nobody has been assigned
- D) already retired
- E) The text does not say.

**Q16** What is unknown about the circuit breaker threshold of 20?
- A) whether it triggers too often
- B) whether it is documented
- C) whether it is right
- D) whether it is too low
- E) The text does not say.

**Q17** What possible secondary cause is mentioned regarding the February config incident?
- A) It stemmed from a third‑party library bug
- B) It was caused by a network outage
- C) It may have had a second cause that was never identified
- D) It was due to a hardware failure
- E) The text does not say.

**Q18** What future load concern has not been modelled?
- A) the effect of the new workflow engine
- B) the latency of the new alert routing
- C) the impact of adding a third replica
- D) whether the end‑of‑month peak will exceed capacity after next quarter's merchant onboarding
- E) The text does not say.

**Q19** What type of backoff is used for retries after the January incident?
- A) linear backoff
- B) exponential backoff
- C) random jitter
- D) fixed interval
- E) The text does not say.

**Q20** What is the name of the job that had an expired TLS certificate?
- A) settlement job
- B) audit job
- C) payment aggregator
- D) reconciliation job
- E) The text does not say.

**Q21** How many days did the expired TLS certificate remain unnoticed?
- A) 6 days
- B) 3 days
- C) 9 days
- D) 12 days
- E) The text does not say.

**Q22** What is the purpose of the second approver introduced after the February incident?
- A) to monitor alerts
- B) to approve configuration changes
- C) to schedule deployments
- D) to review code merges
- E) The text does not say.

**Q23** What is the rule regarding incident note timing?
- A) must be written before the next shift
- B) must be written within 24 hours
- C) must be written within 12 hours
- D) must be written within 48 hours
- E) The text does not say.

**Q24** Which region will host the new third database replica?
- A) ap‑south
- B) eu‑west
- C) us‑east
- D) eu‑central
- E) The text does not say.

**Q25** What is the total error budget allocated for the quarter?
- A) 0.15 percent
- B) 0.20 percent
- C) 0.05 percent
- D) 0.10 percent
- E) The text does not say.

**Q26** What is the name of the job that will be moved off cron?
- A) reconciliation job
- B) settlement job
- C) audit processor
- D) payment collector
- E) The text does not say.

**Q27** What is the planned quarter for adding the third database replica?
- A) completed
- B) not started yet
- C) postponed
- D) already started
- E) The text does not say.

**X01** What is the maximum number of concurrent connections the primary database can handle before performance degrades?
- A) 500 connections
- B) 1,200 connections
- C) 5,000 connections
- D) 2,500 connections
- E) The text does not say.

**X02** Which cloud provider hosts the Meridian payments platform infrastructure?
- A) Google Cloud Platform (GCP)
- B) Microsoft Azure
- C) Amazon Web Services (AWS)
- D) IBM Cloud
- E) The text does not say.

**X03** What is the SLA (Service Level Agreement) uptime guarantee for the Meridian payments platform?
- A) 99.9%
- B) 99.5%
- C) 99.99%
- D) 99.95%
- E) The text does not say.

**X04** Which programming language is primarily used for the reconciliation job that is being migrated off cron?
- A) Go
- B) Ruby
- C) Java
- D) Python
- E) The text does not say.

**X05** What monitoring system is used to track the error budget consumption?
- A) Prometheus
- B) Splunk
- C) New Relic
- D) Datadog
- E) The text does not say.

**X06** What is the retention period for transaction logs in the platform?
- A) 90 days
- B) 30 days
- C) 180 days
- D) 365 days
- E) The text does not say.

**X07** Which authentication method is used for engineers to access the on-call dashboard?
- A) SAML SSO
- B) SSH key pairs
- C) Password only
- D) OAuth2 with MFA
- E) The text does not say.

**X08** What is the average latency for a transaction to be fully settled?
- A) 750 ms
- B) 1.2 seconds
- C) 150 ms
- D) 350 ms
- E) The text does not say.

**X09** Which version control system stores the configuration files for the platform?
- A) GitLab
- B) GitHub
- C) Bitbucket
- D) Azure Repos
- E) The text does not say.

**X10** What is the backup strategy for the primary database?
- A) Full daily backup with hourly incremental
- B) No backup, only replication
- C) Continuous streaming backup to object storage
- D) Weekly full backup with daily incremental
- E) The text does not say.

