# FERPA Compliance Integration Guide for berkeley-dsep-infra/datahub

## Overview

This guide explains how to add FERPA email redaction to the existing workflow in the berkeley-dsep-infra/datahub repository.

## Current Setup (Your Test Repo)

Your working FERPA implementation is in `dispatcher.yaml` as the `ferpa_compliance` job. This job:
- ✅ Masks emails from GitHub Actions logs
- ✅ Redacts emails from issue body
- ✅ Redacts emails from comments
- ✅ Posts FERPA compliance notice

## Integration Steps for datahub Repo

### Step 1: Identify Target Workflow

First, examine the existing workflow in berkeley-dsep-infra/datahub:
- Location: `.github/workflows/<workflow-name>.yaml`
- Look for workflows that:
  - Process issues with data retrieval requests
  - Close issues after processing
  - Handle user email addresses

### Step 2: Extract FERPA Job

Copy the complete `ferpa_compliance` job from your `dispatcher.yaml`:

```yaml
  # FERPA COMPLIANCE - Runs after issue processing
  ferpa_compliance:
    name: FERPA - Redact emails from issue and logs
    runs-on: ubuntu-latest
    needs: [<previous_job_name>]  # Replace with the job that closes the issue
    if: always()  # Run even if previous job fails
    permissions:
      issues: write
    
    steps:
      # Step 1: Extract and mask all emails from logs immediately
      - name: Mask Berkeley emails from workflow logs
        id: mask_emails
        uses: actions/github-script@v7
        with:
          script: |
            const issue = context.payload.issue;
            const issueBody = issue.body || '';
            
            core.info('Issue body length: ' + issueBody.length);
            
            // Extract emails from mailto links first
            const mailtoLinkPattern = /\[([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\]\(mailto:\1\)/gi;
            const mailtoPattern = /mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/gi;
            
            // Multiple email patterns to catch everything
            const berkeleyEmailRegex = /[A-Za-z0-9._%+-]+@berkeley\.edu/gi;
            const genericEmailRegex1 = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi;
            const genericEmailRegex2 = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi;
            
            // Extract all emails using multiple patterns
            const emails = [];
            [mailtoLinkPattern, mailtoPattern, berkeleyEmailRegex, genericEmailRegex1, genericEmailRegex2].forEach(regex => {
              const matches = issueBody.match(regex);
              if (matches) {
                // For mailto patterns, extract just the email part
                if (regex === mailtoPattern) {
                  matches.forEach(match => {
                    const emailMatch = match.match(/mailto:([^)]+)/);
                    if (emailMatch) emails.push(emailMatch[1]);
                  });
                } else if (regex === mailtoLinkPattern) {
                  matches.forEach(match => {
                    const emailMatch = match.match(/\[([^\]]+)\]/);
                    if (emailMatch) emails.push(emailMatch[1]);
                  });
                } else {
                  emails.push(...matches);
                }
              }
            });
            
            // Get unique emails
            const uniqueEmails = [...new Set(emails)];
            
            core.info(`Found ${uniqueEmails.length} email address(es) to mask`);
            
            if (uniqueEmails.length > 0) {
              // Mask all emails from logs
              uniqueEmails.forEach(email => {
                core.setSecret(email);
                core.info(`Masked: ${email.substring(0, 2)}***@***`);
              });
              
              core.info('✅ All email addresses masked from workflow logs');
              return true;
            } else {
              core.warning('⚠️ No email addresses found to mask');
              core.info('Issue body preview: ' + issueBody.substring(0, 300));
              return false;
            }
      
      # Step 2: Redact emails from issue body
      - name: Redact emails from issue body
        uses: actions/github-script@v7
        with:
          script: |
            const issueNumber = context.payload.issue.number;
            
            // Get current issue
            const { data: issue } = await github.rest.issues.get({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: issueNumber
            });
            
            core.info('Original issue body length: ' + (issue.body ? issue.body.length : 0));
            
            // Check if already redacted
            if (issue.body && issue.body.includes('[REDACTED FOR FERPA COMPLIANCE]')) {
              core.info('Issue body already contains FERPA redaction - skipping');
              return false;
            }
            
            if (!issue.body) {
              core.info('Issue body is empty - skipping');
              return false;
            }
            
            // Multiple patterns to catch all formats including markdown mailto links
            let redactedBody = issue.body;
            
            // Pattern 1: Markdown mailto links: [email](mailto:email)
            const mailtoLinkPattern = /\[([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\]\(mailto:\1\)/gi;
            redactedBody = redactedBody.replace(mailtoLinkPattern, '[REDACTED FOR FERPA COMPLIANCE]');
            
            // Pattern 2: Any remaining mailto links with different text
            const mailtoPattern = /\[([^\]]+)\]\(mailto:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\)/gi;
            redactedBody = redactedBody.replace(mailtoPattern, '[REDACTED FOR FERPA COMPLIANCE]');
            
            // Pattern 3: Standard email addresses (most permissive)
            const emailPattern1 = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi;
            
            // Pattern 4: Email addresses with word boundaries
            const emailPattern2 = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi;
            
            // Pattern 5: Berkeley emails specifically
            const berkeleyPattern = /[A-Za-z0-9._%+-]+@berkeley\.edu/gi;
            
            // Apply remaining patterns to catch any non-markdown emails
            const emails = [];
            [emailPattern1, emailPattern2, berkeleyPattern].forEach(pattern => {
              const matches = issue.body.match(pattern);
              if (matches) {
                emails.push(...matches);
              }
            });
            
            // Get unique emails
            const uniqueEmails = [...new Set(emails)];
            
            if (uniqueEmails.length > 0) {
              core.info(`Found ${uniqueEmails.length} email(s) to redact: ${uniqueEmails.map(e => e.substring(0, 3) + '***').join(', ')}`);
              
              // Replace each unique email
              uniqueEmails.forEach(email => {
                // Escape special regex characters in the email for safe replacement
                const escapedEmail = email.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const replaceRegex = new RegExp(escapedEmail, 'gi');
                redactedBody = redactedBody.replace(replaceRegex, '[REDACTED FOR FERPA COMPLIANCE]');
              });
            }
            
            if (redactedBody !== issue.body) {
              core.info('Redacted body preview: ' + redactedBody.substring(0, 200));
              
              // Update issue with redacted body
              await github.rest.issues.update({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: issueNumber,
                body: redactedBody
              });
              
              core.info('✅ Successfully redacted email addresses from issue body');
              return true;
            } else {
              core.info('⚠️ No email addresses found in issue body');
              core.info('Issue body preview: ' + issue.body.substring(0, 300));
              return false;
            }
      
      # Step 3: Redact emails from all issue comments
      - name: Redact emails from issue comments
        uses: actions/github-script@v7
        with:
          script: |
            const issueNumber = context.payload.issue.number;
            
            // Get all comments
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: issueNumber
            });
            
            core.info(`Found ${comments.length} comment(s) to check`);
            
            // Multiple email patterns including markdown mailto links
            const mailtoLinkPattern = /\[([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\]\(mailto:\1\)/gi;
            const mailtoPattern = /\[([^\]]+)\]\(mailto:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\)/gi;
            const emailPattern1 = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi;
            const emailPattern2 = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi;
            const berkeleyPattern = /[A-Za-z0-9._%+-]+@berkeley\.edu/gi;
            
            let redactedCount = 0;
            
            for (const comment of comments) {
              // Skip if this is the FERPA compliance notice itself
              if (comment.body.includes('🔒 FERPA Compliance Notice')) {
                core.info(`Skipping compliance notice comment #${comment.id}`);
                continue;
              }
              
              // Skip if already redacted
              if (comment.body.includes('[REDACTED FOR FERPA COMPLIANCE]')) {
                core.info(`Comment #${comment.id} already redacted - skipping`);
                continue;
              }
              
              // Find all emails in this comment
              const emails = [];
              [mailtoLinkPattern, mailtoPattern, emailPattern1, emailPattern2, berkeleyPattern].forEach(pattern => {
                const matches = comment.body.match(pattern);
                if (matches) {
                  // For mailto patterns, extract just the email part
                  if (pattern === mailtoPattern) {
                    matches.forEach(match => {
                      const emailMatch = match.match(/mailto:([^)]+)/);
                      if (emailMatch) emails.push(emailMatch[1]);
                    });
                  } else if (pattern === mailtoLinkPattern) {
                    matches.forEach(match => {
                      const emailMatch = match.match(/\[([^\]]+)\]/);
                      if (emailMatch) emails.push(emailMatch[1]);
                    });
                  } else {
                    emails.push(...matches);
                  }
                }
              });
              
              const uniqueEmails = [...new Set(emails)];
              
              if (uniqueEmails.length > 0) {
                core.info(`Found ${uniqueEmails.length} email(s) in comment #${comment.id}`);
                
                let redactedBody = comment.body;
                
                // First remove mailto links
                redactedBody = redactedBody.replace(mailtoLinkPattern, '[REDACTED FOR FERPA COMPLIANCE]');
                redactedBody = redactedBody.replace(mailtoPattern, '[REDACTED FOR FERPA COMPLIANCE]');
                
                // Then remove any remaining plain emails
                uniqueEmails.forEach(email => {
                  const escapedEmail = email.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                  const replaceRegex = new RegExp(escapedEmail, 'gi');
                  redactedBody = redactedBody.replace(replaceRegex, '[REDACTED FOR FERPA COMPLIANCE]');
                });
                
                await github.rest.issues.updateComment({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  comment_id: comment.id,
                  body: redactedBody
                });
                redactedCount++;
              }
            }
            
            if (redactedCount > 0) {
              core.info(`✅ Successfully redacted email addresses from ${redactedCount} comment(s)`);
            } else {
              core.info('No email addresses found in comments');
            }
      
      # Step 4: Add FERPA compliance notice to issue
      - name: Add FERPA compliance notice
        uses: actions/github-script@v7
        with:
          script: |
            const issueNumber = context.payload.issue.number;
            
            // Check if notice already exists
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: issueNumber
            });
            
            const noticeExists = comments.some(comment => 
              comment.body.includes('🔒 FERPA Compliance Notice')
            );
            
            if (noticeExists) {
              core.info('FERPA compliance notice already posted - skipping');
              return;
            }
            
            // Add compliance notice
            const noticeBody = [
              '🔒 **FERPA Compliance Notice**',
              '',
              'All email addresses have been automatically redacted from this issue and its comments to comply with the Family Educational Rights and Privacy Act (FERPA).'
            ].join('\n');
            
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: issueNumber,
              body: noticeBody
            });
            
            core.info('✅ FERPA compliance notice posted to issue');
```

### Step 3: Add to Existing Workflow

In the berkeley-dsep-infra/datahub workflow file:

1. **Locate the job that closes the issue** (e.g., `process_request`, `handle_issue`, etc.)

2. **Add the FERPA job after that job:**

```yaml
jobs:
  # ... existing jobs ...
  
  existing_job_that_closes_issue:
    name: Process data request
    # ... existing steps ...
    # Last step should close the issue
  
  # ADD THIS JOB BELOW ⬇️
  ferpa_compliance:
    name: FERPA - Redact emails from issue and logs
    runs-on: ubuntu-latest
    needs: [existing_job_that_closes_issue]  # ⚠️ Update this to match your job name
    if: always()
    permissions:
      issues: write
    
    steps:
      # [Copy all 4 steps from above]
```

### Step 4: Update Job Dependencies

**Critical**: Update the `needs` field to reference the correct job:

```yaml
# BEFORE (your test repo)
needs: test_validation

# AFTER (datahub repo - example names)
needs: process_data_request
# OR
needs: [handle_issue, send_email]  # If multiple jobs need to complete first
```

### Step 5: Ensure Workflow Permissions

Check if the main workflow has `permissions` at the workflow level:

```yaml
name: Data Retrieval Workflow

# Add or verify this exists
permissions:
  issues: write
  contents: read

on:
  issues:
    types: [opened]

jobs:
  # ... rest of workflow
```

If permissions are set at the workflow level, you can remove them from the FERPA job.

### Step 6: Test the Integration

1. **Create a test issue** with a Berkeley email in the datahub repo
2. **Wait for the workflow to complete**
3. **Verify**:
   - ✅ Issue closed (existing functionality)
   - ✅ FERPA job runs after closure
   - ✅ Email redacted from issue body
   - ✅ FERPA notice posted

## Example Integration Pattern

Here's a generic example showing where to add the FERPA job:

```yaml
name: Data Retrieval Workflow

permissions:
  issues: write

on:
  issues:
    types: [opened]

jobs:
  # Step 1: Existing validation job
  validate_request:
    runs-on: ubuntu-latest
    steps:
      - name: Validate issue
        # ... validation logic ...
  
  # Step 2: Existing processing job
  process_request:
    runs-on: ubuntu-latest
    needs: validate_request
    steps:
      - name: Extract data
        # ... extraction logic ...
      
      - name: Send email
        # ... email logic ...
      
      - name: Close issue
        uses: actions/github-script@v7
        with:
          script: |
            await github.rest.issues.update({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.payload.issue.number,
              state: 'closed'
            });
  
  # Step 3: NEW - FERPA compliance job
  ferpa_compliance:
    runs-on: ubuntu-latest
    needs: process_request  # ⚠️ Depends on job that closes issue
    if: always()  # Run even if previous job fails
    permissions:
      issues: write
    steps:
      # [Copy all 4 FERPA steps from Step 2 above]
```

## Key Considerations

### 1. **Trigger Conditions**
The FERPA job should run when:
- ✅ Issue has been closed by previous job
- ✅ Issue contains Berkeley email addresses
- ✅ Issue has specific labels (optional)

### 2. **Label Filtering (Optional)**
If you want FERPA to only run on specific issues:

```yaml
ferpa_compliance:
  name: FERPA - Redact emails
  runs-on: ubuntu-latest
  needs: [previous_job]
  # Only run for issues with "data-request" label
  if: |
    always() &&
    contains(github.event.issue.labels.*.name, 'data-request')
```

### 3. **Error Handling**
The `if: always()` ensures FERPA runs even if the email-sending job fails. This is important because you still want redaction even if something went wrong.

### 4. **Repository Settings**
Ensure the repository has:
- ✅ Actions enabled
- ✅ Workflow permissions set to "Read and write"
  - Settings → Actions → General → Workflow permissions

## Common Integration Patterns

### Pattern A: Single-Job Workflow
If the existing workflow is one job:

```yaml
jobs:
  main_job:
    # ... existing job ...
  
  ferpa_compliance:
    needs: main_job
    # ... FERPA steps ...
```

### Pattern B: Multi-Job Sequential Workflow
If jobs run in sequence:

```yaml
jobs:
  job1:
    # ... 
  job2:
    needs: job1
    # ...
  job3:
    needs: job2
    # ... closes issue
  
  ferpa_compliance:
    needs: job3  # Depends on last job
    # ... FERPA steps ...
```

### Pattern C: Multi-Job Parallel Workflow
If multiple jobs run in parallel:

```yaml
jobs:
  validate:
    # ...
  process_a:
    needs: validate
    # ...
  process_b:
    needs: validate
    # ...
  finalize:
    needs: [process_a, process_b]  # Waits for both
    # ... closes issue
  
  ferpa_compliance:
    needs: finalize  # Depends on finalize
    # ... FERPA steps ...
```

## Troubleshooting

### FERPA Job Not Running

**Check:**
1. Did the previous job close the issue? (FERPA triggers on closure)
2. Is `needs` referencing the correct job name?
3. Are workflow permissions set to `issues: write`?
4. Is the workflow trigger `issues: types: [opened]` present?

### Emails Not Redacted

**Check:**
1. Look at the FERPA job logs for "Found X email(s)"
2. Verify the email format matches the regex patterns
3. Check if issue body has accessible content
4. Ensure job has `issues: write` permission

### Notice Posted Multiple Times

**Check:**
- The idempotency check should prevent this
- Look for the "already posted - skipping" message in logs
- Verify the notice text matches exactly (emoji included)

## Testing Checklist

Before submitting PR to berkeley-dsep-infra/datahub:

- [ ] FERPA job added to correct workflow file
- [ ] `needs` references correct job name
- [ ] Workflow permissions include `issues: write`
- [ ] Created test issue with Berkeley email
- [ ] Verified workflow runs to completion
- [ ] Confirmed email redacted from issue body
- [ ] Confirmed FERPA notice posted
- [ ] Checked no duplicate notices
- [ ] Verified logs don't show full email addresses

## PR Description Template

```markdown
## Summary
Adds FERPA compliance automation to redact Berkeley email addresses from 
data retrieval issues after processing.

## Changes
- Added `ferpa_compliance` job to `<workflow-name>.yaml`
- Runs after `<previous-job>` completes and closes issue
- No modifications to existing jobs or logic

## How It Works
1. Existing workflow processes issue and closes it
2. FERPA job automatically runs (same workflow, separate job)
3. Emails redacted from issue body and comments
4. Compliance notice posted to issue

## Testing
- Tested in fork: <link-to-test-issue>
- Verified email redaction works
- Confirmed existing workflow unaffected
- Checked logs for proper masking

## Benefits
- ✅ FERPA compliant email handling
- ✅ No changes to existing business logic
- ✅ Works with default GITHUB_TOKEN
- ✅ Automatic and transparent to users
```

## Next Steps

1. **Find the workflow file** in berkeley-dsep-infra/datahub that handles data retrieval issues
2. **Identify the job name** that closes the issue
3. **Copy the FERPA job** from Step 2 above
4. **Update `needs`** to reference the correct job
5. **Test in a fork** before submitting PR
6. **Submit PR** with clear documentation

---

## Quick Reference

**Minimum required fields for FERPA job:**
```yaml
ferpa_compliance:
  runs-on: ubuntu-latest
  needs: [<job-that-closes-issue>]
  if: always()
  permissions:
    issues: write
  steps:
    # [4 steps: mask, redact issue, redact comments, post notice]
```

**Files to modify:**
- `.github/workflows/<data-retrieval-workflow>.yaml` (add FERPA job)

**No changes needed to:**
- Issue templates
- Scripts
- Other workflows
- Repository settings (assuming Actions already enabled)

---

**Need help?** Check the workflow logs in Actions tab for detailed error messages and debugging info.
