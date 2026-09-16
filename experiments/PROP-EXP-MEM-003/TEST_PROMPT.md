# Blind handoff prompt

You are receiving a project state from an external system.

Do NOT assume access to any previous conversation.
Do NOT invent missing facts.

Read the supplied state once, then answer these five questions:

1. What is the mission of this project?
2. What is the project's current technical state?
3. What has already failed, and what was learned from those failures?
4. What is the single best next action?
5. What important information is still missing or uncertain?

Then provide:

- Confidence in your reconstruction: 0.00 to 1.00
- Any facts you are unsure about
- One proposed measurable next experiment

Important:
Your job is to reconstruct only from the supplied state.
If information is absent, say that it is absent.
Keep the whole answer under 450 words.
