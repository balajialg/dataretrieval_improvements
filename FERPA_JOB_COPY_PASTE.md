# FERPA Job - Ready to Copy for datahub Repository

## Instructions

1. Open `berkeley-dsep-infra/datahub/.github/workflows/data-retrieval.yaml`
2. Find the job that closes the issue (the last job)
3. Add this entire job **after** that job
4. Update the `needs` field to reference the correct job name

---

## Copy This Code Block ⬇️

```yaml
  # FERPA COMPLIANCE - Add this job at the end of data-retrieval.yaml
  ferpa_compliance:
    name: FERPA - Redact emails from issue and logs
    runs-on: ubuntu-latest
    needs: [REPLACE_WITH_JOB_NAME_THAT_CLOSES_ISSUE]  # ⚠️ UPDATE THIS LINE
    if: always()
    permissions:
      issues: write
    
    steps:
      - name: Mask Berkeley emails from workflow logs
        id: mask_emails
        uses: actions/github-script@v7
        with:
          script: |
            const issueNumber = ${{ inputs.issue_number }};
            
            const { data: issue } = await github.rest.issues.get({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: issueNumber
            });
            
            const issueBody = issue.body || '';
            core.info('Issue body length: ' + issueBody.length);
            
            const mailtoLinkPattern = /\[([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\]\(mailto:\1\)/gi;
            const mailtoPattern = /mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})/gi;
            const berkeleyEmailRegex = /[A-Za-z0-9._%+-]+@berkeley\.edu/gi;
            const genericEmailRegex1 = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi;
            const genericEmailRegex2 = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi;
            
            const emails = [];
            [mailtoLinkPattern, mailtoPattern, berkeleyEmailRegex, genericEmailRegex1, genericEmailRegex2].forEach(regex => {
              const matches = issueBody.match(regex);
              if (matches) {
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
            
            const uniqueEmails = [...new Set(emails)];
            core.info(`Found ${uniqueEmails.length} email address(es) to mask`);
            
            if (uniqueEmails.length > 0) {
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
      
      - name: Redact emails from issue body
        uses: actions/github-script@v7
        with:
          script: |
            const issueNumber = ${{ inputs.issue_number }};
            
            const { data: issue } = await github.rest.issues.get({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: issueNumber
            });
            
            core.info('Original issue body length: ' + (issue.body ? issue.body.length : 0));
            
            if (issue.body && issue.body.includes('[REDACTED FOR FERPA COMPLIANCE]')) {
              core.info('Issue body already contains FERPA redaction - skipping');
              return false;
            }
            
            if (!issue.body) {
              core.info('Issue body is empty - skipping');
              return false;
            }
            
            let redactedBody = issue.body;
            
            const mailtoLinkPattern = /\[([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\]\(mailto:\1\)/gi;
            redactedBody = redactedBody.replace(mailtoLinkPattern, '[REDACTED FOR FERPA COMPLIANCE]');
            
            const mailtoPattern = /\[([^\]]+)\]\(mailto:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\)/gi;
            redactedBody = redactedBody.replace(mailtoPattern, '[REDACTED FOR FERPA COMPLIANCE]');
            
            const emailPattern1 = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi;
            const emailPattern2 = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi;
            const berkeleyPattern = /[A-Za-z0-9._%+-]+@berkeley\.edu/gi;
            
            const emails = [];
            [emailPattern1, emailPattern2, berkeleyPattern].forEach(pattern => {
              const matches = issue.body.match(pattern);
              if (matches) {
                emails.push(...matches);
              }
            });
            
            const uniqueEmails = [...new Set(emails)];
            
            if (uniqueEmails.length > 0) {
              core.info(`Found ${uniqueEmails.length} email(s) to redact: ${uniqueEmails.map(e => e.substring(0, 3) + '***').join(', ')}`);
              
              uniqueEmails.forEach(email => {
                const escapedEmail = email.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const replaceRegex = new RegExp(escapedEmail, 'gi');
                redactedBody = redactedBody.replace(replaceRegex, '[REDACTED FOR FERPA COMPLIANCE]');
              });
            }
            
            if (redactedBody !== issue.body) {
              core.info('Redacted body preview: ' + redactedBody.substring(0, 200));
              
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
      
      - name: Redact emails from issue comments
        uses: actions/github-script@v7
        with:
          script: |
            const issueNumber = ${{ inputs.issue_number }};
            
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: issueNumber
            });
            
            core.info(`Found ${comments.length} comment(s) to check`);
            
            const mailtoLinkPattern = /\[([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\]\(mailto:\1\)/gi;
            const mailtoPattern = /\[([^\]]+)\]\(mailto:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\)/gi;
            const emailPattern1 = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/gi;
            const emailPattern2 = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/gi;
            const berkeleyPattern = /[A-Za-z0-9._%+-]+@berkeley\.edu/gi;
            
            let redactedCount = 0;
            
            for (const comment of comments) {
              if (comment.body.includes('🔒 FERPA Compliance Notice')) {
                core.info(`Skipping compliance notice comment #${comment.id}`);
                continue;
              }
              
              if (comment.body.includes('[REDACTED FOR FERPA COMPLIANCE]')) {
                core.info(`Comment #${comment.id} already redacted - skipping`);
                continue;
              }
              
              const emails = [];
              [mailtoLinkPattern, mailtoPattern, emailPattern1, emailPattern2, berkeleyPattern].forEach(pattern => {
                const matches = comment.body.match(pattern);
                if (matches) {
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
                
                redactedBody = redactedBody.replace(mailtoLinkPattern, '[REDACTED FOR FERPA COMPLIANCE]');
                redactedBody = redactedBody.replace(mailtoPattern, '[REDACTED FOR FERPA COMPLIANCE]');
                
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
      
      - name: Add FERPA compliance notice
        uses: actions/github-script@v7
        with:
          script: |
            const issueNumber = ${{ inputs.issue_number }};
            
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

---

## Critical: Update These Lines

### Line to Change

Find this line in the code above:
```yaml
needs: [REPLACE_WITH_JOB_NAME_THAT_CLOSES_ISSUE]  # ⚠️ UPDATE THIS LINE
```

Replace with the actual job name from `data-retrieval.yaml` that closes the issue. For example:
```yaml
needs: [send_email_and_close]
# or
needs: [finalize_request]
# or whatever the actual job name is
```

---

## Where to Add This

**File**: `.github/workflows/data-retrieval.yaml` in berkeley-dsep-infra/datahub

**Location**: At the very end, after all existing jobs

**Example structure**:
```yaml
# data-retrieval.yaml

name: Data Retrieval

on:
  workflow_call:
    inputs:
      issue_number:
        required: true
        type: number
    secrets:
      DATA_RETRIEVAL_SA:
        required: true
      TOKEN_PICKLE:
        required: true

jobs:
  # ... existing jobs ...
  
  some_job:
    # ... steps ...
  
  another_job:
    # ... steps that close issue ...
  
  # ADD THE FERPA JOB HERE ⬇️
  ferpa_compliance:
    name: FERPA - Redact emails
    # ... paste the code from above
```

---

## Quick Verification

After adding, check:
- ✅ Indentation matches other jobs (starts at same level)
- ✅ `needs` references correct job name
- ✅ All `${{ inputs.issue_number }}` are present (not `github.event.issue.number`)
- ✅ No syntax errors (YAML is sensitive to spacing)

---

## Test in Fork First

1. Fork berkeley-dsep-infra/datahub
2. Add FERPA job to your fork's `data-retrieval.yaml`
3. Create test issue with Berkeley email
4. Verify redaction works
5. Then submit PR to main repo

---

## Questions?

See [DATAHUB_FERPA_INTEGRATION.md](DATAHUB_FERPA_INTEGRATION.md) for detailed explanation and troubleshooting.
