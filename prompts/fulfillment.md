You analyze ONE recorded call where the host delivers to an existing client. Read the ENTIRE transcript. Reply with ONLY one JSON object, no prose, no code fence.

Return:
{
 "client_name": "the client's full name as they introduce themselves or are addressed (the paying client, never a team member)",
 "company": "their business, or \"\"",
 "topic": "what this call covered, max 20 words",
 "confidence": 0.0-1.0
}
If several clients are on the call, use the primary one. If you cannot tell who the client is, client_name = "" and confidence <= 0.4.
