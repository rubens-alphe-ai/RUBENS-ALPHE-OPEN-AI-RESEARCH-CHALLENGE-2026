# Handover: Meridian payments platform, on-call rotation

The platform settles 84,000 transactions a day across 11 merchant regions, on a
cluster of 6 application nodes and 2 database replicas. On-call is a weekly
rotation of 5 engineers; handover happens Monday at 09:00 UTC. The current
runbook version is 4.2, published 12 March 2026, and it supersedes 3.9, which is
still linked from the internal wiki and should not be used.

Throughput averages 58 transactions per second, peaking at 190 during the
end-of-month settlement window on the last working day. The error budget for the
quarter is 0.15 percent of requests; 0.09 percent has been consumed as of the
last review.

Three incidents shaped the current setup. In January 2026 a retry storm took the
primary database to 100 percent CPU for 41 minutes after a downstream provider
began returning 502s; retries are now capped at 3 with exponential backoff and a
circuit breaker opens after 20 consecutive failures. In February 2026 a
configuration push removed the read-replica routing and all traffic hit the
primary; config changes now require a second approver and are applied to one
region first. In March 2026 an expired TLS certificate on the reconciliation job
went unnoticed for 6 days because its alert routed to a decommissioned channel;
every alert route is now verified monthly against the on-call directory.

Four rules are in force. No deployment between 16:00 UTC Friday and 09:00 UTC
Monday. Any change to settlement logic requires a replay against the previous
day's traffic before merge. A region may be drained by the on-call engineer
alone, but restoring it needs a second engineer. Incident notes are written
within 24 hours or the incident is reopened.

Planned work: migrating the reconciliation job off cron to the workflow engine,
scheduled for Q3 and blocked on a dependency upgrade; adding a third database
replica in the eu-west region, approved but not started; and retiring runbook
3.9 from the wiki, which nobody has been assigned.

Open questions. It is not known whether the circuit breaker threshold of 20 is
right, because it has not opened in production since it was introduced. The
February config incident may have had a second cause that was never identified.
Whether the end-of-month peak will exceed capacity after the merchant onboarding
planned for next quarter has not been modelled.
