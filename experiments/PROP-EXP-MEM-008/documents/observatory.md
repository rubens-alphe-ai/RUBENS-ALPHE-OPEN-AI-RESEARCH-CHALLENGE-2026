# Handover: Mont Ventoux small observatory, instrument and data operations

The observatory operates a 60-centimetre reflector installed in 2017 and a 20-centimetre
refractor used for public outreach. Useful nights average 195 a year; 2024 had 168 because of an
unusually wet autumn. Data volume is about 400 gigabytes a month, archived to a university server
in Marseille with a nightly transfer that takes 40 minutes.

The main camera was replaced in March 2025 after its cooling system failed twice; the new sensor
has 30 percent lower read noise but requires a firmware update the team has not yet applied,
because the update requires taking the instrument offline for a full night.

Two incidents are on record. In 2023 a dome rotation motor seized during a session and the
telescope tracked into the dome wall, bending a counterweight rod; the rod was replaced and a
limit switch added. In February 2025 three weeks of photometry were lost because a timestamp
offset of 1.2 seconds went unnoticed after a clock synchronisation change; timestamps are now
checked against a GPS reference at the start of every session.

Rules in force: no observation runs during public outreach evenings, because the 2023 incident
happened while both were scheduled together. Raw frames are never deleted, only compressed after
two years. Any change to the acquisition software requires a test night before production use.

A collaboration with a Spanish observatory for simultaneous observations was proposed in 2025;
it depends on a shared scheduling tool that nobody has evaluated. It is not known whether the
current network link can carry simultaneous transfers.
