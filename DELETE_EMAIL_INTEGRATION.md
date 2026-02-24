# Delete-Email Workflow: Integration Guide for datahub

## What This Does

When the `delete-email` label is added to a data retrieval issue, this workflow:

1. **Redacts** all email addresses from the issue body and comments
2. **Deletes** the successful dispatcher workflow run (removing logs that contain emails)
3. **Keeps** failed workflow runs intact for debugging
4. **Posts** a FERPA compliance notice on the issue
5. **Removes** the `delete-email` label (cleanup)

## Architecture

```
Issue #8053 opened with "data retrieval" label
    ↓
dispatcher.yaml → data-retrieval.yaml runs, emails user, closes issue
    ↓
Admin adds "delete-email" label to issue #8053
    ↓
delete-email.yaml triggers:
    • Redacts emails from issue body & comments
    • Finds dispatcher run matching issue title
    • Deletes the run if conclusion == 'success'
    • Posts FERPA compliance notice
    • Removes 'delete-email' label
```

**Key safety property**: This workflow is completely separate from the existing
`dispatcher.yaml` and `data-retrieval.yaml`. It does NOT modify them.

---

## Setup (One-Time)

### 1. Create the `delete-email` label

In `berkeley-dsep-infra/datahub`:
- Go to **Issues → Labels → New label**
- Name: `delete-email`
- Color: `#d73a49` (red) — or any color
- Description: `Trigger FERPA email redaction and workflow log cleanup`

### 2. Add the workflow file

Copy `.github/workflows/delete-email.yaml` to the datahub repo on the
`test-dataretrieval-workflow` branch:

```bash
# Clone or checkout the datahub repo
git clone https://github.com/berkeley-dsep-infra/datahub.git
cd datahub
git checkout -b test-dataretrieval-workflow staging

# Copy the workflow file
cp /path/to/delete-email.yaml .github/workflows/delete-email.yaml
git add .github/workflows/delete-email.yaml
git commit -m "Add delete-email workflow for FERPA email redaction"
git push origin test-dataretrieval-workflow
```

### 3. Verify Actions permissions

Go to **Settings → Actions → General → Workflow permissions**:
- Ensure **"Read and write permissions"** is selected
- This is needed for `actions: write` (to delete runs) and `issues: write` (to edit issues)

---

## Testing Strategy

### Important: Issue events only trigger workflows from the default branch

The `issues: [labeled]` trigger only runs workflow files from the **default branch**
(likely `staging`). So you can NOT test the label trigger from a feature branch.

**Two options for testing:**

### Option A: Use `workflow_dispatch` (Recommended for initial testing)

The workflow includes a manual trigger that works **from any branch**:

1. Push the workflow to `test-dataretrieval-workflow` branch
2. Go to **Actions → "Delete Email from Data Retrieval"**
3. Select the `test-dataretrieval-workflow` branch
4. Click **"Run workflow"** and enter an issue number
5. Watch the run and verify behavior

This lets you iterate safely without merging to the default branch.

### Option B: Merge to staging and use the label

Once you're confident from `workflow_dispatch` testing:

1. Create a PR from `test-dataretrieval-workflow` → `staging`
2. Merge the PR
3. Create a **test issue** with "data retrieval" label + a test email
4. Wait for the data retrieval workflow to run
5. Add the `delete-email` label
6. Verify the redaction and run deletion

---

## Testing Checklist

### Pre-merge testing (via `workflow_dispatch`)

- [ ] Workflow runs without errors on a test issue
- [ ] Emails redacted from issue body
- [ ] Emails redacted from comments
- [ ] FERPA compliance notice posted
- [ ] Successful dispatcher run deleted
- [ ] Failed dispatcher runs kept
- [ ] No duplicate FERPA notices on re-run
- [ ] Workflow skips non-"data retrieval" issues gracefully

### Post-merge testing (via label trigger)

- [ ] Adding `delete-email` label triggers the workflow
- [ ] `delete-email` label removed after completion
- [ ] Existing data-retrieval workflow unaffected
- [ ] Re-adding `delete-email` label is safe (idempotent)

---

## How Workflow Run Matching Works

The workflow finds dispatcher runs to delete by:

1. **Listing** all workflows in the repo, finding `dispatcher.yaml` by path
2. **Filtering** runs: `event = 'issues'` and `created >= issue_created_date`
3. **Matching** by `display_title === issue.title`
   - GitHub sets the run's `display_title` to the issue title for issue-triggered workflows
4. **Deleting** only runs where `conclusion === 'success'`
5. **Keeping** runs where `conclusion !== 'success'` (for debugging)

### Why this matching is reliable

- Issue titles from the data retrieval form template include unique details
  (student info, folder paths) making them effectively unique
- The `event: 'issues'` filter eliminates non-issue-triggered runs
- The `created` date filter narrows the search window
- Only `conclusion === 'success'` runs are deleted — failed runs are always preserved

---

## Safety Guarantees

| Concern | How it's handled |
|---------|-----------------|
| Breaks existing workflow? | No — this is a separate file, doesn't touch dispatcher.yaml or data-retrieval.yaml |
| Deletes wrong run? | Matches by exact issue title + event type + success status |
| Email leaked in delete-email logs? | All emails are `core.setSecret()`-masked in step 2 |
| Double-processing? | Idempotent: checks "already redacted", "notice already posted" |
| Failed data retrieval? | Keeps the run for debugging; still redacts emails from the issue |
| Label left on issue? | Auto-removed after processing; manual dispatch skips removal |

---

## Rollback

To remove this feature entirely:
1. Delete `.github/workflows/delete-email.yaml` from the repo
2. Optionally delete the `delete-email` label

No other files are affected. Existing workflows continue to work unchanged.

---

## PR Description Template

```markdown
## Summary
Adds a `delete-email` workflow that redacts PII (email addresses) from data
retrieval issues and deletes the associated workflow run logs for FERPA compliance.

## Changes
- New file: `.github/workflows/delete-email.yaml`
- New label: `delete-email`

## How It Works
1. Admin adds `delete-email` label to a completed data retrieval issue
2. Workflow redacts all emails from issue body and comments
3. Workflow deletes the successful dispatcher run (logs with emails)
4. FERPA compliance notice posted to the issue

## Safety
- Separate workflow file — zero modifications to existing workflows
- Only deletes successful runs; keeps failed runs for debugging
- Idempotent — safe to trigger multiple times
- Uses default GITHUB_TOKEN — no PAT or secrets needed
- Includes `workflow_dispatch` trigger for safe testing before merge

## Testing
- Tested via `workflow_dispatch` on `test-dataretrieval-workflow` branch
- Verified on issue #___: emails redacted, run deleted, notice posted
- Confirmed existing data-retrieval workflow unaffected
```
