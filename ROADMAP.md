# Indaba Roadmap & Wishlist

Ideas captured from Discord (via `!idea`) and development sessions, ordered by date added.
Use this file to track what to build next — reviewed and prioritised during each Claude Code session.

---

## Ideas

<!-- New ideas are appended here automatically by Indaba Bot -->

### Bulk Send from People Mode
_Added: 2026-04-23_

Compose a WhatsApp message, select multiple leads it should go out to (checkbox list, filterable by pipeline), then choose "Send Now" or "Send Later" with the datetime picker. A single composed message would be cloned per recipient and queued individually on EC2. Useful for outreach campaigns across a pipeline stage (e.g., send a follow-up to all "Enquiry" leads in the Subscriptions pipeline at once).

### Pipeline-Filtered Outreach Statistics
_Added: 2026-04-23_

The Outreach stats dashboard currently shows total messages sent across all pipelines. Add a pipeline filter so you can view stats scoped to one pipeline at a time — e.g., "Messages sent this week under Subscriptions" or "Messages sent this week under Retreats." Would also be useful to see per-stage breakdowns (how many messages went to Enquiry leads vs Qualified leads). Possible UI: a pipeline selector dropdown above the stats table that re-fetches with a `pipeline_id` query param.
