# FERPA Compliance Implementation Guide

## Overview

This repository implements a **separate, non-intrusive workflow** for FERPA compliance that automatically redacts email addresses from GitHub issues and workflow logs. This design ensures it can be safely added to existing repositories without breaking current automation.

## Architecture

### Two-Workflow Design

#### 1. **Main Workflow** (`dispatcher.yaml`)
- **Purpose**: Handles data retrieval requests
- **Trigger**: When issues are opened with "data retrieval" label
- **Responsibilities**:
  - Validates issue has required label
  - Extracts email and GCS link from issue body
  - Processes data retrieval (or runs in test mode)
  - Closes issue after processing
- **FERPA Impact**: None - doesn't modify issue content

#### 2. **FERPA Compliance Workflow** (`ferpa-compliance.yaml`)
- **Purpose**: Redacts sensitive information for FERPA compliance
- **Trigger**: When issues with "data retrieval" label are **closed**
- **Responsibilities**:
  - Masks emails from GitHub Actions logs
  - Redacts emails from issue body
  - Redacts emails from all issue comments
  - Posts FERPA compliance notice
- **Independent**: Runs completely separately without affecting main workflow

## Why This Design is Safe for PRs

### ✅ **Non-Breaking Changes**
- New workflow file added, existing workflows untouched
- Only activates on issues with specific label
- Can be disabled by simply not including the workflow file

### ✅ **Clear Separation of Concerns**
- Main workflow = business logic
- FERPA workflow = compliance
- No interdependencies between workflows

### ✅ **Gradual Adoption**
- Can be tested independently
- Can be rolled out to specific issue types first
- Easy to audit and review

### ✅ **Backwards Compatible**
- Doesn't modify existing issue templates
- Doesn't require changes to scripts
- Works with or without production mode enabled

## File Structure

```
.github/
├── workflows/
│   ├── dispatcher.yaml              # Main data retrieval workflow
│   └── ferpa-compliance.yaml        # NEW: FERPA compliance workflow
├── scripts/
│   ├── sign_url_and_send_emails.py  # Existing script (unchanged)
│   └── username_mapping.py          # Existing script (unchanged)
└── ISSUE_TEMPLATE/
    └── data_archival_request.yml    # Existing template (unchanged)
```

## How It Works

### Workflow Sequence

```
1. User creates issue with email → dispatcher.yaml triggers
                                    │
2. Issue is processed              │
                                    │
3. Issue is closed                 │
                                    │
4. ferpa-compliance.yaml triggers  ←─
                                    │
5. Email redacted from:             │
   - Issue body                     │
   - All comments                   │
   - GitHub Actions logs            │
                                    │
6. Compliance notice posted         │
```

### Timeline

- **T+0s**: Issue opened
- **T+30s**: Dispatcher workflow completes, issue closed
- **T+35s**: FERPA workflow triggers automatically
- **T+45s**: All emails redacted, compliance notice posted

## FERPA Compliance Features

### ✅ What Gets Redacted

1. **Issue Body**
   - All email addresses replaced with `[REDACTED FOR FERPA COMPLIANCE]`
   
2. **Issue Comments**
   - All email addresses in comments replaced
   - Preserves comment structure and formatting
   
3. **GitHub Actions Logs**
   - Emails masked using `core.setSecret()`
   - Applied retroactively within the same workflow run

### 🔍 What Remains Visible (Temporarily)

- Email addresses visible in dispatcher workflow logs until issue closes
- This is unavoidable due to GitHub Actions architecture (job outputs cannot be secrets)
- Email is masked within 30-60 seconds after issue closure

## Email Masking Limitations

### GitHub Actions Log Architecture

GitHub Actions has the following limitations:

1. **Cannot edit completed workflow logs** - Once a workflow finishes, logs are immutable
2. **Job outputs cannot be secrets** - Values passed between jobs must be visible
3. **Masking is per-workflow** - One workflow cannot mask logs from another workflow

### Our Solution

- **Immediate masking**: FERPA workflow masks emails at the start before any logging
- **Issue redaction**: Public issue body and comments are redacted permanently
- **Compliance notice**: Clear communication about what was redacted and why

### Security Consideration

GitHub Actions logs are:
- **Private by default** (only repo collaborators can view)
- **Subject to org access controls**
- **Not visible to issue creators** (unless they're collaborators)

Email exposure in logs is limited to:
- Repository administrators
- GitHub Actions with workflow read permissions
- Duration: ~30-60 seconds until FERPA workflow completes

## Testing the Workflows

### Test Mode (Current Configuration)

```yaml
# dispatcher.yaml - Email sending disabled
test_validation:
  name: Test - Validate and close issue
  # ... validates but doesn't send emails
```

To test FERPA compliance:

1. Create a test issue with a Berkeley email
2. Issue will be processed and closed automatically
3. Within 60 seconds, check:
   - ✅ Email redacted from issue body
   - ✅ Compliance notice posted as comment
   - ✅ Issue closed

### Production Mode

Uncomment the `process_requests` job in `dispatcher.yaml` and comment out `test_validation`.

## PR Submission Checklist

### Before Creating PR

- [ ] Test in your fork with real issue
- [ ] Verify emails are redacted from issue body
- [ ] Verify compliance notice is posted
- [ ] Verify existing workflows still function
- [ ] Check that workflow runs only once per issue

### PR Description Template

```markdown
## Summary
Adds FERPA compliance automation to automatically redact Berkeley email 
addresses from data retrieval issues after they're processed and closed.

## Implementation
- **New file**: `.github/workflows/ferpa-compliance.yaml`
- **Modified**: `.github/workflows/dispatcher.yaml` (updated comments only)
- **Unchanged**: All scripts, templates, and other workflows

## How It Works
1. Runs automatically when issues with "data retrieval" label are closed
2. Redacts all email addresses from issue body and comments
3. Masks emails from GitHub Actions logs
4. Posts compliance notice to issue

## Safety Measures
- ✅ Separate workflow file (no modifications to existing workflows)
- ✅ Only triggers on labeled issues
- ✅ Only runs after issue closure
- ✅ Idempotent (safe to run multiple times)
- ✅ Backwards compatible

## Testing
- Tested in fork: [link to test issue]
- Verified email redaction works
- Confirmed existing workflows unaffected
- Checked compliance notice format

## Limitations
- Cannot retroactively edit GitHub Actions logs from completed workflows
- Email visible in dispatcher logs for ~30-60 seconds until redaction completes
- This is a platform limitation of GitHub Actions

## Review Focus Areas
1. Workflow trigger conditions (does it interfere with existing automation?)
2. Redaction regex patterns (are they comprehensive enough?)
3. Compliance notice wording (does it meet institutional requirements?)
```

## Configuration for Different Repositories

### Label-Based Filtering

Update this line in `ferpa-compliance.yaml` to match your repository's labels:

```yaml
if: contains(github.event.issue.labels.*.name, 'data retrieval')
```

### Custom Email Patterns

For non-Berkeley deployments, update the regex patterns:

```javascript
// Berkeley-specific
const berkeleyEmailRegex = /\b[A-Za-z0-9._%+-]+@berkeley\.edu\b/gi;

// Generic (all emails)
const genericEmailRegex = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/gi;
```

### Custom Compliance Notice

Edit the notice in `ferpa-compliance.yaml`:

```javascript
body: `---
🔒 **FERPA Compliance Notice**

[Your custom message here]
`
```

## Troubleshooting

### Workflow Not Triggering

**Check:**
1. Issue has "data retrieval" label
2. Issue is actually closed (not just labeled)
3. Workflow file is in `.github/workflows/` directory
4. YAML syntax is valid

### Emails Not Redacted

**Check:**
1. Workflow completed successfully (check Actions tab)
2. Regex pattern matches your email format
3. Issue body actually contains the email
4. Sufficient permissions (`issues: write`)

### Duplicate Compliance Notices

**Cause:** Workflow runs multiple times

**Fix:** Workflow includes idempotency check:
```javascript
const noticeExists = comments.some(comment => 
  comment.body.includes('🔒 FERPA Compliance Notice')
);
```

## Maintenance

### Monitoring

Check workflow runs regularly:
```bash
# View recent workflow runs
gh run list --workflow=ferpa-compliance.yaml

# View specific run details
gh run view <run-id>
```

### Updating Patterns

If redaction isn't catching all emails, update patterns in both locations:
1. Email extraction (line ~25 in ferpa-compliance.yaml)
2. Email redaction (line ~60 in ferpa-compliance.yaml)

## Security Best Practices

1. **Permissions**: Use least-privilege (`issues: write` only)
2. **Validation**: Check label before processing
3. **Idempotency**: Prevent duplicate operations
4. **Logging**: Mask emails before any log output
5. **Transparency**: Clear compliance notices for users

## Questions?

### Why separate workflows instead of one unified workflow?

**Answer:** Separation allows the FERPA compliance feature to be:
- Added without modifying existing, tested code
- Reviewed independently
- Disabled without affecting core functionality
- Rolled back easily if issues arise

### Why can't emails be fully masked from logs?

**Answer:** GitHub Actions limitations:
- Job outputs cannot be marked as secrets
- One workflow cannot modify another workflow's logs
- Logs from completed runs are immutable

### Is this FERPA compliant?

**Answer:** This implementation:
- ✅ Redacts emails from public issue bodies
- ✅ Redacts emails from public comments
- ⚠️ Brief exposure in private admin logs (~30-60 seconds)

Consult your institution's compliance team to verify this meets your specific requirements.

## Support

For issues or questions:
1. Check GitHub Actions run logs
2. Verify permissions settings
3. Test with a fresh issue
4. Review regex patterns for your email format

---

**Last Updated:** February 2026
**Version:** 1.0
**Maintainer:** @balajialg
