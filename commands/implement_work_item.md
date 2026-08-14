---
description: Implement an Azure DevOps work item end-to-end (checks, plan approval, branch, task-tracked implementation)
argument-hint: <work-item-id>
---

Implement work item **$ARGUMENTS** (PBI, Bug, Tech Debt Item, Spike, SSRD, etc) using the `ado_work_item_mcp` MCP tools. Follow this procedure exactly, in order. Do not skip or reorder steps.

## 0. Repo context check

Confirm you are currently running inside the local git repository that corresponds to this work item's implementation. If it is not clear from the work item's title/description which repo that is, or you have any doubt you're in the right one, **stop and ask the user** rather than assuming.

## 1. Initial checks (read-only)

Call `get_work_item(work_item_id)` and evaluate, in order:

1. **State check** — the work item's `state` must be `Approved` or `Committed`. If it is any other state, warn the user which state it's actually in and **do not proceed** with anything below.
2. **Grooming check** — the work item's `effort` field must be non-empty. If it is empty, warn the user it isn't groomed and **ask for explicit permission before continuing**. Do not proceed on your own judgment.

Only move to step 2 once both checks pass (or the user explicitly overrides the grooming warning).

## 2. Branch

Ask the user which base branch to create the new branch from — unless they already told you in their request. Ask for (or use an already-established) branch naming convention, e.g. a prefix such as `<your-prefix>/<short-descriptive-name>`, off the chosen base branch.

## 3. Draft a plan (no writes yet)

Draft an implementation plan for the work item and present it to the user for review. **Do not write any code or attach anything until the user approves this plan.** Iterate on it based on their feedback.

## 4. Capture and attach the plan

Once approved, write the plan as PLAN.md content and call `attach_plan(work_item_id, content)`.

**Before attaching, scrub the content** — it must not contain local file paths, secrets, keys, tokens, or any other sensitive/environment-specific detail. Describe the approach in terms a reader outside your machine could understand (repo-relative concepts, not absolute paths or credentials).

This `attach_plan` call is the **only** write action you are allowed to perform on the work item itself. Do not call `set_work_item_state` or `add_work_item_comment` on this work item as part of this procedure, now or later in the flow.

## 5. Implement

You have a free hand on implementation approach. As you work:

- Create child tasks under the work item as you see fit (`create_task`), each with a `title`, `description`, and `effort` (a human-style estimate for that task, as if a person had sized it). Task `description` fields support markdown — format them with it (headings, lists, code spans, etc.) rather than as flat prose.
- Keep task `state` current as you progress: `New` → `In Progress` → `Done`. Update tasks (`update_task`) as work moves along rather than only at the end.
- Do not touch the work item's own state or comments — only its child tasks change during implementation.

## 6. Verification
Once implementation is done, you must verify the implementation. This can be done by executing unit tests or instrumentation tests or any way that you see fit. Before you start the verification, you must create a child task under the work item (`create_task`), by populating `title`, `description` (where you detail how the verification is done) and `effort`. You may then proceed with the verification and propagate the task accordingly.

## 7. User Review
After the implementation and verification is done, you must report it to user and ask them to review it. Once they confirm, you proceed to the next step. Otherwise, the user may ask queries or suggest changes that you must consider. You may only proceed to the next step after user confirmation (and must ask about the confirmation to the user explicitly).

## 8. Pull Request Creation
Once the user approves the changes, you must do the following:

- Check if the git repo points to a GitHub Remote. If yes, proceed with PR creation, else tell the user that PRs can only be raised to Github and stop.
- Commit the changes with a suitable commit message.
- Create 2 child tasks under the work item (`create_task`), one with `title` as "Raise PR to feature branch" and other with `title` as "Merge PR to feature branch". As `description` you can mention the associated branches. `effort` should be 1.
- Check if `gh` (github CLI) is accessible.
- Prepare a PR from the working branch to the branch the working branch was branched off from.
- Include `AB#<work-item-id>` somewhere in the PR title or description — this is Azure Boards' GitHub linking convention and auto-links the PR back to this work item once the connection processes the webhook (works even if added by editing an already-open PR, not just at creation).
- Consider any pull request templates present in the repo. If you find a template, you must fill the body as per the template.
- Show user about the PR details and ask confirmation, once confirmed, raise the PR else stop.
