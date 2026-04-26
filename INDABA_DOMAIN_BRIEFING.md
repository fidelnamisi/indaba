# INDABA — Domain Model & UI/UX Briefing Document

**Prepared for:** Intermediary Coding Agent  
**Version:** 1.0  
**Date:** 31 March 2026

---

## 1. Purpose of This Document

This document defines the domain model for the Indaba application and provides precise instructions for redesigning the application's UI and UX to reflect that domain model accurately.

The intermediary Coding Agent must read this document in full, inspect the existing codebase, and produce detailed instructions for the final Coding Agent to implement the changes described here.

Two foundational concepts govern everything in Indaba. They are referred to throughout this document using these exact terms and must be used consistently in all code, comments, variable names, component names, and documentation:

- **Content Schema** — the structural definition of what content is made of (the nouns: Works, Modules, Essential Assets, Supporting Assets)
- **Content Workflow** — the operational stages that every Module moves through (the verbs: Producing, Publishing, Promoting)

---

## 2. Content Schema

The Content Schema defines the hierarchy and composition of all content in the system. Every piece of content belongs to a Work. Every Work is divided into Modules. Every Module has one Essential Asset and a set of Supporting Assets.

### 2.1 Schema Table

| Work | Module | Module Description | Essential Asset | Supporting Assets |
|---|---|---|---|---|
| Book | Chapter | A discrete unit of the book's narrative | Chapter Prose | Tagline, Blurb, Excerpts, Images, Key Art, Header Image |
| Podcast | Episode | A single installment of the podcast series | Audio Recording | Title, Show Notes (Blurb), Transcript, Audiogram Clips, Cover Art |
| Fundraising Campaign | Campaign Phase | A stage in the fundraising journey (e.g. Awareness, Appeal, Update) | Written Campaign Narrative (per phase) | Images, Progress Updates, Testimonials, Short Excerpts, Headline, CTA Snippets |
| Retreat (Event) | Invitation / Session | Overall retreat offer OR a specific session within the retreat | Event Offer Write-up (Invitation Page Content) | Images, Schedule Breakdown, Speaker Bios, Testimonials, Pricing Tiles, CTA Snippets |

### 2.2 Rules

- Every Module must have exactly one Essential Asset. A Module cannot be considered complete without it.
- Supporting Assets are optional unless explicitly marked required for a specific Work type.
- The Content Schema drives what fields and asset slots the UI renders for any given Module.
- Work types that support Modules: `Book`, `Podcast`, `Fundraising Campaign`, `Retreat (Event)`.
- `Subscription` is a Work type for cataloguing CRM products (e.g. Patreon tiers, newsletter plans). **Subscription Works do not have Modules.** They are not content-production units — they are the products you are selling. They are managed via the CRM pipeline (People → Pipeline), not the content workflow. Their presence in the Works catalog serves one purpose: to give the New Lead modal a validated dropdown of subscribable products when creating a Subscription pipeline lead.

---

## 3. Content Workflow

The Content Workflow defines the three stages every Module must pass through from creation to sales. This is the operational engine of Indaba. **It is currently not reflected anywhere in the UI and must be implemented as a primary interface element.**

### 3.1 Workflow Table

| Work | Module | Producing | Publishing | Promoting |
|---|---|---|---|---|
| Book | Chapter | Write and finalise chapter prose; generate supporting assets (blurb, tagline, images). | Publish chapter on website, email platform, or reading hub for broad audience access. | Send excerpts/messages via WhatsApp/email; move readers through pipeline to subscribe or purchase full book. |
| Podcast | Episode | Record, edit, and finalise audio; create show notes and supporting media. | Publish episode on podcast platforms (Spotify, Apple) and website for public streaming. | Share clips and links; engage listeners directly; convert into subscribers, supporters, or paid members. |
| Fundraising Campaign | Campaign Phase | Write phase-specific narrative (story, need, ask); create visuals and proof elements. | Publish on fundraising platforms (GoFundMe), website, and social pages for visibility. | Reach out individually; guide donors through pipeline from awareness to commitment and contribution. |
| Retreat (Event) | Invitation | Write event offer (details, value, logistics); create visuals and supporting content. | Publish on website, landing page, and event platforms for public access and registration. | Engage prospects one-on-one; guide through interest, qualification, and commitment to book and attend. |

### 3.2 Stage Definitions

#### Producing
The creation stage. All assets (essential and supporting) are generated and finalised here. A Module in Producing is not ready to be published. The system must track which assets are complete, missing, or optional.

#### Publishing
The distribution stage. The finished Module is pushed to the relevant external platforms. Each Work type has specific platforms associated with it. Publishing status must be tracked per platform.

#### Promoting
The sales and engagement stage. This stage has two layers, both of which must be present in the UI:

- **Broadcast layer (one-to-many):** Broadcast Posts, Messages, Outbox, Serializer — tools for mass outreach.
- **CRM layer (one-to-one):** Contacts and Deals — tracking individual prospects and moving them through the sales pipeline (`Lead > Qualified > Proposal > Negotiation > Closed`).

> **IMPORTANT:** Contacts and Deals are NOT separate management tools. They are the CRM layer of the Promoting stage. They must be accessible within the Promoting context of a Module, not as standalone top-level navigation items.

---

## 4. Navigation Redesign

The current navigation (`Execute | Create | Manage`) must be replaced entirely. The new navigation is built around the Content Workflow.

### 4.1 Remove: Execute

The Execute screen (Operational Brain) is to be removed. Its functionality — surfacing next actions and pipeline health — is replaced by the new Content Workflow Pipeline Overview (see Section 5).

### 4.2 Remove and Decouple: Create

The Create section (Creative Ledger — stories, treatments, world bible, etc.) is to be fully removed from the Indaba codebase. **This is not a deletion — it is a migration.**

- All code related to the Create section must be cleanly extracted and moved to a separate, standalone codebase.
- The new codebase will be entirely independent: different repo, different folder structure, different app name.
- Nothing from the Create section should remain in the Indaba codebase — not a file, not a folder, not an import, not a route.
- Before executing the migration, the Coding Agent must produce a full manifest of all Create-related files, routes, components, and database models.

> **IMPORTANT:** The Create section is a different product. It is being separated, not discarded. Preserve all code integrity during extraction.

### 4.3 New Top-Level Navigation

Replace the current nav bar with the following:

| Nav Item | What It Is | Replaces |
|---|---|---|
| `Pipeline` | Content Workflow Pipeline Overview (Section 5) | Execute + Manage > Inventory |
| `Works` | Browse and manage all Works and their Modules with full Content Schema and Workflow status | Manage > Inventory + Serializer |
| `Promote` | Broadcast layer + CRM layer (Contacts, Deals, Messages, Broadcast Posts, Outbox) | Manage > Contacts + Deals + Broadcast Posts + Messages + Outbox |
| `⚙` Settings icon | App configuration (AI providers, delivery schedule, WhatsApp branding, CTA links) | Manage > Settings — accessed via top-right icon, replacing the Plugins button |

- The Plugins button is to be deprecated and removed.
- Settings moves to a gear icon in the top-right corner of the nav bar.

---

## 5. Pipeline Overview Screen

This is the new home screen of Indaba. It replaces both the Execute screen and the Inventory screen as the primary operational view.

### 5.1 Layout

#### Work Type Filter Bar (top)
A horizontal filter bar allowing the user to filter the pipeline by Work type.  
Options: `All | Book | Podcast | Campaign | Event`  
Default: `All`

#### Three Metric Cards (middle)
Three cards displayed side by side — one per workflow stage: `Producing`, `Publishing`, `Promoting`.

Each card shows:
- Stage name
- Total count of Modules currently in that stage
- Brief breakdown by Work type (e.g. `2 books · 1 podcast · 1 event`)
- A slim colour-coded bar showing proportional distribution by Work type
- Clicking a card selects it and populates the drill-down list below
- The active card is highlighted with a `1.5px` border

#### Drill-Down List (bottom)
A list of Modules in the selected stage. Each row shows:
- Module title
- Parent Work name
- Work type badge (colour-coded: Book = purple, Podcast = teal, Campaign = amber, Event = coral)
- An `Open` button linking to the Module detail view

The drill-down list updates instantly when the user selects a different stage card. No page reload.

---

## 6. Module Detail View

When a user opens any Module (from the Pipeline Overview or from the Works screen), they see the Module detail view. This view must expose both the Content Schema (what the module is made of) and the Content Workflow (where it is in its journey).

### 6.1 Layout

#### Header
- Breadcrumb: `Work Name > Module Name`
- Module title (large, prominent)
- Module metadata: Work type · Parent Work name · Last updated date

#### Stage Status Bar (3 clickable cards, below header)
Three cards in a horizontal row, one per stage.

Each card shows:
- Stage number and name (`Stage 1: Producing` / `Stage 2: Publishing` / `Stage 3: Promoting`)
- A slim progress bar showing completion percentage for that stage
- A brief stat line (e.g. `3 of 5 assets done` / `0 of 3 platforms` / `1 of 3 actions done`)
- Clicking a card selects it and updates the detail panel below
- The active card is highlighted with a `1.5px` green border

#### Detail Panel (below stage bar)
A single panel whose content changes based on the selected stage card. The panel header names the active stage.

**Producing panel:**
- Section: `Essential Asset` — one row: asset name, status dot (green = done, red = missing), action button (`View` or `Generate`)
- Section: `Supporting Assets` — one row per asset with the same pattern
- Status dots: green = done, red = missing, grey = optional

**Publishing panel:**
- Section: `Platforms` — one row per relevant platform for the Work type
- Each row: platform name + published status
- A `Mark as Published` action button

**Promoting panel:**
- Section: `Broadcast Actions` — rows for WhatsApp broadcast, email excerpt, serializer post, each with `Queue` or `Sent` status
- Section: `CRM` — link to view/add Contacts and Deals associated with this specific Module

---

## 7. Promote Screen

The Promote screen consolidates all outreach and sales tools. It has two layers accessible via sub-navigation or a toggle within the screen.

### 7.1 Broadcast Layer (one-to-many)
- Broadcast Posts — existing functionality, retained as-is
- Messages (Message Maker) — existing functionality, retained as-is
- Outbox — existing functionality, retained as-is
- Serializer — existing functionality, retained as-is

### 7.2 CRM Layer (one-to-one)
- Contacts — existing functionality, retained as-is
- Deals — existing functionality, retained as-is (Kanban: `Lead > Qualified > Proposal > Negotiation > Closed`)

The CRM layer must also be accessible contextually from within any Module's Promoting panel (see Section 6).

---

## 8. Instructions for the Intermediary Coding Agent

### 8.1 Codebase Audit Tasks

Before issuing any implementation instructions, the intermediary agent must:

1. Identify all files, components, routes, and database models related to the Create section (Creative Ledger). Produce a full manifest with file paths.
2. Identify all files related to the Execute screen (Operational Brain). Mark for removal.
3. Map every existing route to its replacement in the new navigation structure.
4. Identify any existing data model fields that correspond to `producing`, `publishing`, `promoting` status. Assess whether they need to be added, renamed, or restructured.
5. Identify all references to `Execute`, `Create`, and `Manage` in the codebase (routes, nav components, labels) and map each to its replacement or removal.

### 8.2 Implementation Instructions to Issue

The intermediary agent must produce step-by-step instructions covering:

- **Extract Create section:** Provide exact file paths and a migration manifest. All files move to a new standalone codebase. Nothing remains in Indaba.
- **Remove Execute screen:** Provide exact files and routes to delete.
- **Rebuild top navigation:** Provide exact component structure for the new nav (`Pipeline | Works | Promote | ⚙`).
- **Build Pipeline Overview screen:** Implement the Dashboard + drill-down layout per Section 5.
- **Build Module detail view:** Implement the Stage Status Bar + Detail Panel layout per Section 6.
- **Restructure Promote screen:** Consolidate Broadcast and CRM layers per Section 7.
- **Move Settings:** Remove Plugins button, add Settings gear icon to top-right nav.
- **Update Module data model:** Add `producing_status`, `publishing_status`, `promoting_status` fields if not already present.
- **Enforce naming conventions:** See Section 8.3.

### 8.3 Naming Conventions to Enforce

The final Coding Agent must use these exact terms in all component names, variable names, route names, and comments:

| Term | Meaning | Use In |
|---|---|---|
| `contentSchema` | The structure of a Work — its Modules and Assets | Component names, props, DB model references |
| `contentWorkflow` | The three operational stages of a Module | Component names, state variables, route names |
| `workflowStage` | One of: `producing`, `publishing`, `promoting` | Enum values, status fields, filter keys |
| `essentialAsset` | The single required asset for a Module | Field names, UI labels |
| `supportingAsset` | Any optional or secondary asset for a Module | Field names, UI labels |
| `broadcastLayer` | One-to-many promotion tools | Component grouping, sub-nav labels |
| `crmLayer` | One-to-one contacts and deals tools | Component grouping, sub-nav labels |

---

## 9. Summary of Changes

| Change | Action | Priority |
|---|---|---|
| Create section (Creative Ledger) | Extract and move to new standalone codebase. Remove all traces from Indaba. | Critical |
| Execute screen (Operational Brain) | Remove entirely. | Critical |
| Top navigation | Replace `Execute \| Create \| Manage` with `Pipeline \| Works \| Promote` + Settings icon. | Critical |
| Pipeline Overview screen | Build new screen: Dashboard metric cards + drill-down list, filtered by Work type. | Critical |
| Module detail view | Add Stage Status Bar + Detail Panel to every Module view. | Critical |
| Promote screen | Consolidate Broadcast Posts, Messages, Outbox, Serializer, Contacts, Deals into unified Promote screen. | High |
| Settings | Move to top-right icon. Remove Plugins button. | Medium |
| Workflow stage data model | Add `producing_status`, `publishing_status`, `promoting_status` to Module model if absent. | High |
| Naming conventions | Enforce `contentSchema`, `contentWorkflow`, `workflowStage` throughout codebase. | High |

---

*End of briefing document.*
