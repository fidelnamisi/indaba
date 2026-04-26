# Cowork Job: Universal Message Queue Dispatch (The Bucket)

This document defines the interface for Cowork to manage the automated dispatch of all Indaba communications via the GOWA WhatsApp server. This includes scheduled invites, subscription alerts, and FIFO content like proverbs and stories.

## Core Interaction

Cowork should be configured to hit the following endpoint on a recurring schedule (e.g., every 30 minutes, or at specific peak times).

**Endpoint:** `POST /api/promo/sender/pop_next`  
**Authentication:** Internal Network / Basic Auth (admin:admin)

## Dispatch Logic

Indaba handles the intelligent selection of the next job from the "Bucket" (`promo_messages.json`):

1.  **Priority 1: Timed Messages.** Any message where `scheduled_at` <= "Now".
2.  **Priority 2: FIFO (First In, First Out).** Any message with no scheduled time (e.g., approved proverbs).
3.  **Process:** Indaba sends the message (text or image) to the GOWA engine and records the results.

## Prompt / Instruction for Cowork

When Cowork is assigned the Task "Process Indaba Send Queue", it should:

1.  Attempt to `POST` to `http://localhost:5050/api/promo/sender/pop_next`.
2.  **Success (`{"ok": true}`):** The message was sent. Mark the job as successful.
3.  **Empty (`{"ok": false, "message": "Queue is empty"}`):** No messages found. Job complete.
4.  **No Due (`{"ok": false, "message": "No messages due..."}`):** Items exist but are scheduled for later. Job complete.
5.  **Error:** Retry after 5 minutes, then notify the user.

## Management & Control

Users manage the queue in the **GOWA Send Queue** tab within the Promotion Machine on the Indaba dashboard. Here, messages can be:
-   **Previewed** (with status and source tracking).
-   **Edited** (text, recipient, or schedule adjustments).
-   **Deleted** (removed from the bucket before dispatch).
