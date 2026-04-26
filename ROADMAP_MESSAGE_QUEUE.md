# Universal Message Queue Roadmap

## Phase 1: Data Architecture & Unified Backend

### **Objective:** Consolidate all module-specific communications into a single, centralized "Bucket" (`promo_messages.json`).

*   **Task 1.1: Unified Schema Expansion.** Ensure all messages (proverbs, invites, notifications) support `source_module`, `scheduled_at`, `priority`, and `media_url` fields.
*   **Task 1.2: Advanced Selection Logic.** Refactor the Selection Engine to prioritize:
    1.  **Timed Messages**: Where `scheduled_at` <= `now`.
    2.  **FIFO Messages**: Where `scheduled_at` is null (e.g., Proverbs).
*   **Task 1.3: "Process Next" Global Endpoint.** Create `/api/promo/sender/send_next_global` that determines the best message to send across all categories.

## Phase 2: Centralized Management Dashboard ("GOWA Send Queue")

### **Objective:** Provide a transparent, premium UI for managing the "Bucket".

*   **Task 2.1: Unified Queue Tab.** Transform the current "Sender" sub-tab into a comprehensive "Message Queue Control" panel.
*   **Task 2.2: Universal CRUD.**
    *   **Edit:** Support in-place editing of text, recipient, and scheduled time.
    *   **Delete:** Remove any pending message from the queue.
    *   **Status Badges:** Visual indicators for `queued` (timed), `pending` (FIFO), `dispatched`, `sent`, and `failed`.
*   **Task 2.3: Module Linking.** Add "Go to Source" links for messages (e.g., link back to the proverb gallery or the contact record).

## Phase 3: Module Integration & Bridge-Building

### **Objective:** Connect the specialized modules (WA Post Maker, Publishing Central) to the unified bucket.

*   **Task 3.1: Proverb Bridge.** Modify the `Approve` action in "WA Post Maker" to move approved proverbs into the `promo_messages.json` queue as FIFO tasks.
*   **Task 3.2: Module Standardization.** Standardize the `POST` payload across all modules when adding to the queue.

## Phase 4: Cowork & Audit

### **Objective:** Ensure Cowork dispatches are flawless and the system hits a 100% Audit Score.

*   **Task 4.1: Cowork Job Definitions.** Update `COWORK_SEND_INSTRUCTIONS.md` for the unified `send_next_global` logic.
*   **Task 4.2: Audit Tool.** Implement a dedicated diagnostic view or log that tracks every GOWA attempt and Cowork interaction.
*   **Task 4.3: UX/UI Polish.** Review accessibility, responsiveness, and premium aesthetics.

## Phase 5: End-to-End Testing & Score Audit

*   **Task 5.1: 5-Point functional test.** (Bulk Generate → Approve → Audit Queue → Send via Cowork → Reconcile).
*   **Task 5.2: Final Production Build & Performance Tuning.**
