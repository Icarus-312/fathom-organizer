You analyze ONE recorded SALES call. Read the ENTIRE transcript. Reply with ONLY one JSON object, no prose, no code fence.

outcome (judge only from what happens on the call):
- "won": clear yes: agreed to buy, paid, enrolled, or signed on the call.
- "lost": clear no, or the prospect disqualifies themselves or the host disqualifies them, with no next step.
- "follow_up": undecided, "let me think", or a next step / second call was agreed.

Return:
{
 "prospect": "full name of the prospect",
 "company": "their business, or \"\"",
 "outcome": "won|lost|follow_up",
 "outcome_evidence": "short VERBATIM quote from the transcript that proves the outcome",
 "objections": [{"objection": "short label (e.g. price, timing, need to ask spouse, trust, already have a provider)", "quote": "VERBATIM", "overcome": true|false}],
 "next_step": "what was agreed next, or \"\"",
 "one_line": "what this prospect wanted, max 20 words"
}
Rules: list only objections the PROSPECT actually raised. overcome=true only if the prospect moved past it on the call. Never invent quotes; if there is no clean quote use "". If there are no objections use [].
