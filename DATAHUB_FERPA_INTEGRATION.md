# FERPA Integration for berkeley-dsep-infra/datahub

## Repository Structure Analysis

**Dispatcher workflow**: `.github/workflows/dispatcher.yaml`
```yaml
jobs:
  dispatch-data-retrieval:
    if: contains(toJson(github.event.issue.labels), 'data retrieval')
    uses: ./.github/workflows/data-retrieval.yaml  # Calls reusable workflow
    with:
      issue_number: ${{ github.event.issue.number }}
    secrets:
      DATA_RETRIEVAL_SA: ${{ secrets.DATA_RETRIEVAL_SA }}
      TOKEN_PICKLE: ${{ secrets.TOKEN_PICKLE }}
```

**Reusable workflow**: `.github/workflows/data-retrieval.yaml`
- This workflow posts success comment and closes the issue
- See: https://github.com/berkeley-dsep-infra/datahub/actions/runs/21897054757/job/63215515801

## Recommended Approach: Add FERPA to `data-retrieval.yaml`

Since `data-retrieval.yaml` is the workflow that closes the issue, add the FERPA job **there** as the final job. This ensures it runs right after issue closure.

---

## Implementation

### Step 1: Modify `data-retrieval.yaml`

Location: `berkeley-dsep-infra/datahub/.github/workflows/data-retrieval.yaml`

**Add this job at the end of the jobs section:**

```yaml
# At the end of data-retrieval.yaml, after the job that closes the issue

  ferpa_compliance:
    name: FERPA - Redact emails from issue and logs
    runs-on: ubuntu-latest
    needs: [<job_name_that_closes_issue>]  # Replace with actual job name
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
            const issueNumber = ${{ inputs.issue_number }};
            
            // Get the issue (since this is a reusable workflow, we use inputs)
            const { data: issue } = await github.rest.issues.get({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: issueNumber
            });
            
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
            const issueNumber = ${{ inputs.issue_number }};
            
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
            const issueNumber = ${{ inputs.issue_number }};
            
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
            const issueNumber = ${{ inputs.issue_number }};
            
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

### Step 2: Key Differences for Reusable Workflows

**Important changes from your test repo:**

1. **Issue number access**: Uses `${{ inputs.issue_number }}` instead of `context.payload.issue.number`
   - Reusable workflows receive inputs, not direct event context

2. **Must fetch issue data**: First step gets the issue via API since `context.payload.issue` isn't available

3. **Dependencies**: Update `needs: [<job_name>]` to reference the job that closes the issue in `data-retrieval.yaml`

### Step 3: Find the Job Name

You need to identify the job in `data-retrieval.yaml` that closes the issue. Look for a job with a step like:

```yaml
- name: Close issue
  uses: actions/github-script@v7
  with:
    script: |
      await github.rest.issues.update({
        issue_number: ...,
        state: 'closed'
      });
```

Then update the `needs` field in the FERPA job:

```yaml
ferpa_compliance:
  needs: [actual_job_name_here]  # Replace with the real job name
```

---

## Alternative Approach: Add to `dispatcher.yaml`

If you prefer to keep FERPA logic separate from the reusable workflow:

**In `dispatcher.yaml`:**

```yaml
jobs:
  dispatch-data-retrieval:
    if: contains(toJson(github.event.issue.labels), 'data retrieval')
    uses: ./.github/workflows/data-retrieval.yaml
    with:
      issue_number: ${{ github.event.issue.number }}
    secrets:
      DATA_RETRIEVAL_SA: ${{ secrets.DATA_RETRIEVAL_SA }}
      TOKEN_PICKLE: ${{ secrets.TOKEN_PICKLE }}
  
  # Add FERPA job here
  ferpa_compliance:
    name: FERPA - Redact emails from issue and logs
    runs-on: ubuntu-latest
    needs: [dispatch-data-retrieval]
    if: always()
    permissions:
      issues: write
    
    steps:
      # Use the same 4 steps as above
      # BUT change all instances of:
      #   const issueNumber = ${{ inputs.issue_number }};
      # TO:
      #   const issueNumber = ${{ github.event.issue.number }};
```

**Pros:**
- Keeps FERPA logic in dispatcher (single place to review)
- No changes to reusable workflow

**Cons:**
- Slight delay between issue closure and FERPA redaction
- Less clear that FERPA is part of data retrieval process

---

## Recommendation

**Use Option 1**: Add FERPA job to `data-retrieval.yaml`

**Why?**
- Follows the same pattern as your test repo
- Runs immediately after issue closure
- More maintainable (the workflow doing the work also does cleanup)
- Guaranteed to run in the context of the data retrieval process

---

## Testing Steps

1. **Create fork** of berkeley-dsep-infra/datahub
2. **Add FERPA job** to `data-retrieval.yaml`
3. **Create test issue** with "data retrieval" label and Berkeley email
4. **Wait for workflow** to complete
5. **Verify**:
   - ✅ Issue processed and closed (existing behavior)
   - ✅ FERPA job runs after closure
   - ✅ Email redacted from issue body
   - ✅ FERPA notice posted
6. **Check logs**: Ensure no full emails visible in Actions logs

---

## PR Checklist

- [ ] FERPA job added to `.github/workflows/data-retrieval.yaml`
- [ ] `needs` references correct job name (the one that closes issues)
- [ ] Changed `context.payload.issue.number` to `${{ inputs.issue_number }}`
- [ ] Workflow permissions include `issues: write` (check workflow-level or job-level)
- [ ] Tested in fork with real issue
- [ ] Verified email redaction works
- [ ] Confirmed FERPA notice appears
- [ ] Checked no duplicate notices
- [ ] Examined logs to ensure emails masked

---

## Summary

**File to modify**: `.github/workflows/data-retrieval.yaml`

**What to add**: One new job (`ferpa_compliance`) with 4 steps at the end

**Key changes from test repo**:
- Use `${{ inputs.issue_number }}` instead of `context.payload.issue.number`
- Fetch issue data in first step (since it's a reusable workflow)
- Update `needs` to reference the job that closes the issue

**No changes needed**:
- `dispatcher.yaml` (stays the same)
- Issue templates
- Scripts
- Other workflows
