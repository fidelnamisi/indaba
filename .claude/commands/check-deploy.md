Check whether the most recent EC2 deployment succeeded.

Steps:
1. Use the mcp__github__issue_read tool with method "get_comments", owner "fidelnamisi", repo "indaba", issue_number 1, perPage 3 to fetch the latest smoke-proverb deploy reports.
2. If comments exist, read the most recent one and summarise: did the deploy succeed? Is the app serving? Any errors?
3. If no comments exist, report that no post-deploy report is available yet and suggest waiting 2–3 minutes for the smoke-proverb workflow to complete, then running /check-deploy again.
4. End with one of: "✓ Deploy confirmed healthy", "✗ Deploy failed — <reason>", or "⏳ Report not yet available."
