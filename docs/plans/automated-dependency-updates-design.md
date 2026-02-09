# Automated Dependency Updates with Dependabot and Mergify

**Date:** 2026-02-09
**Status:** Proposal
**Author:** Engineering Team

## Executive Summary

This document proposes enabling Dependabot and Mergify to automate dependency updates with a focus on rapid CVE remediation. Security updates (critical/high CVEs) will auto-merge when all CI checks pass, while non-security updates will require manual review. This reduces the time to remediate vulnerabilities from days/weeks to hours while maintaining control over feature updates.

## Goals

### Primary Goal
- **Avoid critical and high-severity CVEs** by automating security patches

### Secondary Goals
- Reduce manual toil in dependency management
- Keep dependencies current to reduce technical debt
- Maintain audit trail of all dependency changes
- Free up developer time for feature work

## Background

### Current State

The project currently manages dependencies through:
- **Python:** `requirements.in` → `pip-compile` → architecture-specific lockfiles
- **JavaScript:** Two npm projects (admin portal, chatbot) with `package.json`/`package-lock.json`
- **GitHub Actions:** Workflow dependencies pinned in YAML files

Existing automation:
- `pip_compile.yml` - Validates lockfiles match `.in` files
- `pip_audit.yml` / `npm_audit.yml` - Security vulnerability scanning
- Pre-commit hooks for code quality

**Gaps:**
- No automated monitoring for new dependency versions
- Manual effort required to identify and apply security patches
- CVE response time depends on developer availability
- No systematic process for non-security updates

### Proposed State

**Dependabot** monitors dependencies daily and creates PRs for updates.

**Mergify** auto-merges security updates that pass all CI/CD checks.

**Result:** CVE remediation time reduced from days to hours.

## Architecture

### Two-Tier Update Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                        Dependabot                            │
│                  (Daily Monitoring)                          │
└────────────┬────────────────────────────┬───────────────────┘
             │                            │
             ▼                            ▼
    ┌────────────────┐          ┌─────────────────┐
    │   Security     │          │  Non-Security   │
    │   Updates      │          │    Updates      │
    │  (CVE Fixes)   │          │ (Features/Deps) │
    └────────┬───────┘          └────────┬────────┘
             │                           │
             ▼                           ▼
    ┌────────────────┐          ┌─────────────────┐
    │  All CI Checks │          │  Manual Review  │
    │      Pass?     │          │    Required     │
    └────────┬───────┘          └─────────────────┘
             │
             ▼
    ┌────────────────┐
    │    Mergify     │
    │  Auto-Merge    │
    └────────────────┘
```

### Ecosystems Monitored

| Ecosystem | Location | Update Frequency | Auto-Merge |
|-----------|----------|------------------|------------|
| Python (pip) | `requirements.in` | Daily | Security only |
| npm (Admin Portal) | `ansible_ai_connect_admin_portal/package.json` | Daily | Security only |
| npm (Chatbot) | `ansible_ai_connect_chatbot/package.json` | Daily | Security only |
| GitHub Actions | `.github/workflows/*.yml` | Daily | Security only |

### PR Strategy

**Individual PRs per dependency** (not grouped):
- Easier rollback if specific update causes issues
- Clear attribution when issues arise
- Independent merge/reject decisions
- Maximum granularity

**Limit:** 5 open PRs per ecosystem to prevent overwhelming the queue.

## Detailed Design

### 1. Dependabot Configuration

**File:** `.github/dependabot.yml`

**Key settings:**
- `interval: daily` - Check for updates every day
- `open-pull-requests-limit: 5` - Prevent PR spam
- Auto-label PRs: `dependencies`, `security`, `python`/`javascript`/`github-actions`
- Commit message prefix: `deps:` for dependencies, `ci:` for Actions

**Special handling for Python:**
- Dependabot updates only `requirements.in`
- Separate workflow runs `pip-compile` to regenerate lockfiles
- Ensures architecture-specific lockfiles stay in sync

**Version constraints:**
- Major version updates ignored by default (too risky for auto-merge)
- Minor and patch updates allowed
- Security updates override all constraints

### 2. Mergify Configuration

**File:** `.github/mergify.yml`

**Auto-merge conditions (ALL must be true):**
1. Author is `dependabot[bot]`
2. PR has label `security`
3. All required CI checks pass:
   - **Python:** pre-commit, selftest (pip_compile), pip_audit, pyright
   - **Admin Portal:** pre-commit, ui_compile, npm_audit
   - **Chatbot:** pre-commit, ui_compile_chatbot, npm_audit_chatbot
   - **GitHub Actions:** pre-commit
4. Zero change requests from reviewers
5. Zero pending review requests
6. No merge conflicts

**Merge method:** Squash merge
- Keeps history clean
- Single commit per dependency update
- Easy to revert if needed

**Branch cleanup:** Auto-delete branch after merge

**Non-security updates:**
- Auto-approve with comment
- Do NOT auto-merge
- Remain open for manual review

### 3. pip-compile Integration

**File:** `.github/workflows/dependabot_pip_compile.yml` (new)

**Purpose:** Auto-update Python lockfiles when Dependabot updates `requirements.in`

**Workflow:**
1. Trigger on PR changes to `requirements.in` or `requirements-dev.in`
2. Check if author is `dependabot[bot]`
3. Run `make pip-compile` to regenerate lockfiles
4. Commit updated lockfiles back to the Dependabot PR branch
5. CI re-runs with updated lockfiles
6. Mergify sees passing tests and auto-merges

**Permissions:** Requires `contents: write` to push commits to Dependabot branch

### 4. Labels and Organization

**Dependabot applies:**
- `dependencies` - All dependency updates
- `security` - Security vulnerabilities only (triggers auto-merge)
- `python` - Python ecosystem
- `javascript` - npm ecosystem
- `admin-portal` - Admin portal specific
- `chatbot` - Chatbot specific
- `github-actions` - Workflow dependencies

**Additional labels (manual):**
- `no-auto-merge` - Disable Mergify for specific PR (requires config update)


## Rollback Procedures

### If a Security Update Breaks Production

**Immediate rollback:**
```bash
# Find the problematic commit
git log --oneline --author="dependabot" -10

# Revert the squash commit
git revert <commit-hash>
git push origin main

# Deploy reverted version
```

**Pin the problematic version:**

Edit `requirements.in` or `package.json`:
```python
# Temporarily pin due to issue #XYZ
package-name==1.2.3
```

Dependabot will respect the pin and won't create update PRs until you remove it.

**Disable auto-merge temporarily:**

Add label `no-auto-merge` to future Dependabot PRs for that package. Requires Mergify config update:

```yaml
# Add to conditions:
- -label=no-auto-merge
```

### If Dependabot Creates Too Many PRs

Adjust `open-pull-requests-limit` in `dependabot.yml`:
```yaml
open-pull-requests-limit: 2  # Reduced from 5
```

### If Auto-Merge is Too Aggressive

**Option 1:** Require manual approval trigger:
```yaml
# Add to Mergify conditions:
- "#approved-reviews-by>=1"
```

**Option 2:** Add time delay before merge:
```yaml
# Add to Mergify actions:
merge:
  method: squash
  delay: "1h"  # Wait 1 hour before merging
```

## Edge Cases and Limitations

### Case 1: Update Requires Code Changes

**Example:** Django major version requires migration scripts.

**Handling:**
- Dependabot creates PR
- pip-compile fails (migrations not run)
- Auto-merge blocked by failing check
- Manual intervention required
- **This is desired behavior**

### Case 2: Conflicting Dependency Requirements

**Example:** Package A requires `requests>=2.31`, Package B requires `requests<2.31`

**Handling:**
- Dependabot detects conflict, creates PR with notes
- pip-compile fails
- Auto-merge blocked
- Manual resolution required (update Package B or find alternative)

### Case 3: Transitive Dependency CVE

**Example:** CVE in `urllib3` (dependency of `requests`)

**Handling:**
- Dependabot updates `requests` to version with fixed `urllib3`
- Labels as `security`
- Auto-merges if tests pass
- **Works correctly**

### Case 4: False Positive Security Advisory

**Example:** CVE doesn't apply to how you use the package

**Handling:**
- Dependabot creates PR anyway
- **Option 1:** Dismiss the advisory in GitHub Security tab (prevents future PRs)
- **Option 2:** Let it auto-merge (defense in depth approach)

### Case 5: Multiple Conflicting Dependabot PRs

**Example:** Both `Django` and `djangorestframework` have updates that conflict

**Handling:**
1. First PR to pass tests auto-merges
2. Second PR becomes conflicted
3. Dependabot auto-rebases the second PR
4. Re-runs tests
5. Auto-merges if passes after rebase

## Testing and Validation Plan

### Phase 1: Dependabot Only (Week 1)

**Actions:**
- Enable `.github/dependabot.yml`
- Comment out all Mergify auto-merge rules
- Wait for 5-10 PRs to be created

**Validation:**
- [ ] Dependabot creates PRs daily
- [ ] Labels applied correctly (`dependencies`, `security`, ecosystem labels)
- [ ] pip-compile workflow triggers and commits lockfiles
- [ ] CI checks run on all PRs
- [ ] Manually merge 3-5 PRs to validate process

### Phase 2: Mergify Dry-Run (Week 2)

**Actions:**
- Enable `.github/mergify.yml` with action: `comment` instead of `merge`
- Mergify comments "Would auto-merge" on qualifying PRs

**Validation:**
- [ ] Mergify comments only on security PRs
- [ ] Mergify respects all conditions (labels, checks, reviews)
- [ ] No false positives (non-security PRs commented)
- [ ] Manually merge commented PRs to validate safety

### Phase 3: Limited Rollout - GitHub Actions (Week 3)

**Actions:**
- Enable auto-merge for `github-actions` ecosystem only
- Monitor for 1 week

**Validation:**
- [ ] At least 1 GitHub Actions security update auto-merges
- [ ] No production issues
- [ ] Workflow changes don't break CI/CD
- [ ] Team comfortable with process

### Phase 4: Full Rollout (Week 4+)

**Actions:**
- Enable auto-merge for Python
- Enable auto-merge for npm (admin portal)
- Enable auto-merge for npm (chatbot)
- Monitor closely for 2 weeks

**Validation:**
- [ ] Security PRs auto-merge within 24 hours
- [ ] Non-security PRs remain open for review
- [ ] No production incidents from auto-merged updates
- [ ] Team retrospective: any concerns?

### Ongoing Validation

**Weekly:**
- Review Mergify dashboard for auto-merged PRs
- Check for any failed auto-merge attempts (investigate why)

**Monthly:**
- Audit all merged security PRs
- Measure CVE remediation time
- Review open Dependabot PRs (should be < 10)

**Quarterly:**
- Full dependency audit
- Update ignored dependencies list
- Review and adjust Mergify rules based on learnings

## Monitoring and Alerts

### Mergify Dashboard

**Access:** `https://dashboard.mergify.com/github/<org>/ansible-ai-connect-service`

**Provides:**
- List of all auto-merged PRs
- Merge queue status
- Rule match history
- Failed merge attempts with reasons

### GitHub Notifications

**Enable notifications for:**
- Security advisories (Settings → Security & analysis → Dependabot alerts)
- Dependabot pull requests
- Failed workflow runs
- Mergify status checks

**Recommended:** Subscribe to email or Slack notifications for:
- Security advisories (critical/high only)
- Failed Dependabot PR merges

### Metrics to Track

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Mean time to remediate CVE | < 24 hours | GitHub Security Advisories dashboard |
| Auto-merge success rate | > 95% | Mergify dashboard |
| Reverted security updates | < 1 per quarter | Git history: `git log --grep="Revert.*dependabot"` |
| Dependabot PR backlog | < 10 open PRs | GitHub PR list filtered by `author:dependabot` |
| Developer time saved | ~2-4 hours/week | Team survey |
| Test coverage | > 80% | `code_coverage.yml` results |

### Slack Integration (Optional)

Add to Mergify rules to notify team:
```yaml
actions:
  merge:
    method: squash
  comment:
    message: |
      :robot: Security update auto-merged
      :rocket: Deployed to production in ~15 minutes
```

## Benefits and Risks

### Benefits

1. **Faster CVE Response**
   - Current: Days to weeks (manual process)
   - Proposed: Hours (automated)
   - Impact: Reduced security exposure window

2. **Reduced Manual Toil**
   - Current: 2-4 hours/week checking for updates
   - Proposed: 0-1 hours/week reviewing non-security updates
   - Impact: Developer time freed for features

3. **Consistent Updates**
   - Current: Ad-hoc, depends on developer initiative
   - Proposed: Daily automated checks
   - Impact: Dependencies stay current, less technical debt

4. **Audit Trail**
   - All updates tracked in git history
   - Clear commit messages with CVE references
   - Easy to trace when/why dependencies changed

5. **Compliance**
   - Demonstrates proactive security posture
   - Automated process for auditors to verify
   - Reduces compliance burden

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking change auto-merged | Low | High | Comprehensive test suite required (>70% coverage); easy revert with squash commits; 2-week validation period |
| Test coverage gaps | Medium | Medium | Monitor post-merge for 24-48 hours; improve tests over time; rollback procedure documented and tested |
| Dependency conflicts | Low | Low | pip-compile validates Python deps; npm lockfiles catch JS conflicts; failed checks block auto-merge |
| Alert fatigue | Medium | Low | Limited to 5 PRs per ecosystem; adjustable to weekly; can group updates |
| Supply chain attack | Very Low | High | npm/pip audit workflows catch known malware; only applies to packages already in use; monitor security advisories |

**Overall Risk Level:** Low to Medium (acceptable for most projects with good CI/CD)

## Cost Considerations

### Dependabot
- **Cost:** FREE (native GitHub feature)
- **Limits:** Unlimited repositories, unlimited PRs
- **Setup:** Zero additional configuration needed

### Mergify
- **Open Source:** FREE if repository is public
- **Private Repositories:**
  - Starter: $8/month (5 developers)
  - Team: $24/month (15 developers)
  - Enterprise: Custom pricing
- **Trial:** 14 days free

**Total Cost:** $0-$24/month depending on team size and repository visibility.

### Alternative Considered

GitHub native auto-merge (free) was considered but rejected because:
- Less flexible rule configuration
- Harder to set up complex conditions
- No dashboard/analytics
- More Actions workflow code to maintain

Mergify provides better value for the small cost.

## Success Metrics

### Key Performance Indicators

**Track monthly:**

1. **CVE Remediation Time**
   - Measure: Time from CVE disclosure to merge
   - Target: < 24 hours average
   - Source: GitHub Security Advisories

2. **Auto-Merge Success Rate**
   - Measure: % of security PRs that auto-merge successfully
   - Target: > 95%
   - Source: Mergify dashboard

3. **Reverted Updates**
   - Measure: Number of auto-merged PRs that were reverted
   - Target: < 1 per quarter
   - Source: Git history

4. **Dependabot PR Backlog**
   - Measure: Number of open Dependabot PRs
   - Target: < 10 at any time
   - Source: GitHub PR list

5. **Developer Time Saved**
   - Measure: Hours per week not spent on dependency updates
   - Target: 2-4 hours/week
   - Source: Team survey

6. **Test Coverage**
   - Measure: Code coverage percentage
   - Target: > 80%
   - Source: `code_coverage.yml` workflow

### Monthly Review Checklist

- [ ] Review all auto-merged PRs for issues
- [ ] Check for recurring test failures on Dependabot PRs
- [ ] Validate no security regressions introduced
- [ ] Adjust Mergify rules if needed based on learnings
- [ ] Update ignored dependencies list (remove stale pins)
- [ ] Generate metrics report
- [ ] Team retrospective (every quarter)

## Documentation Updates

### README.md

Add new section after "Using pre-commit":

```markdown
## Automated Dependency Updates

This project uses Dependabot and Mergify to automatically manage dependencies and security updates.

### How It Works

1. **Dependabot** checks daily for dependency updates across:
   - Python packages (requirements.in)
   - npm packages (admin portal & chatbot)
   - GitHub Actions

2. **Security updates** (CVEs) are automatically merged when:
   - All CI/CD tests pass
   - No merge conflicts exist
   - No change requests from reviewers

3. **Non-security updates** create PRs for manual review

### Managing Dependabot PRs

**To approve a non-security update:**
- Review the PR changes and test results
- Click "Merge pull request" in GitHub UI

**To reject an update:**
- Close the PR with a comment explaining why
- Or add to `.github/dependabot.yml`:
  ```yaml
  ignore:
    - dependency-name: "package-name"
      versions: ["x.y.z"]
  ```

**To temporarily pin a version:**
```python
# In requirements.in, add comment:
package-name==1.2.3  # Pinned due to issue #XYZ
```

**To disable auto-merge for a specific PR:**
- Request changes in a review
- OR add label `no-auto-merge` (requires Mergify config update)

### Monitoring

- **Security advisories:** GitHub Security tab
- **Merged updates:** Check commits by `dependabot[bot]`
- **Mergify dashboard:** https://dashboard.mergify.com
- **Metrics:** Monthly report in team meeting
```

### CONTRIBUTING.md (if exists)

Add section on handling Dependabot PRs for maintainers.

## Implementation Checklist

### Phase 1: Preparation (Week 1)

- [ ] Review current test coverage (ensure > 70%)
- [ ] Document rollback procedures (this document)
- [ ] Sign up for Mergify account at https://mergify.com
- [ ] Create `.github/dependabot.yml` (see configuration above)
- [ ] Create `.github/mergify.yml` with auto-merge DISABLED (comment action only)
- [ ] Create `.github/workflows/dependabot_pip_compile.yml`
- [ ] Update `README.md` with documentation
- [ ] Update `CONTRIBUTING.md` (if exists)
- [ ] Notify team via Slack/email about upcoming changes
- [ ] Schedule weekly check-ins for next 4 weeks

### Phase 2: Dependabot Validation (Week 2)

- [ ] Enable Dependabot (commit `dependabot.yml`)
- [ ] Enable pip-compile workflow (commit `dependabot_pip_compile.yml`)
- [ ] Wait for 5-10 PRs to be created
- [ ] Verify labels applied correctly
- [ ] Verify pip-compile workflow runs and commits lockfiles
- [ ] Manually review and merge 3-5 PRs
- [ ] Check for any conflicts or issues
- [ ] Team check-in: any concerns?

### Phase 3: Mergify Dry-Run (Week 3)

- [ ] Enable Mergify with `comment` action (commit `mergify.yml`)
- [ ] Wait for 3-5 security PRs
- [ ] Review "would auto-merge" comments
- [ ] Validate conditions match only security PRs
- [ ] Validate all required checks listed correctly
- [ ] Manually merge commented PRs
- [ ] Adjust Mergify rules if needed
- [ ] Team check-in: confident to proceed?

### Phase 4: Limited Rollout (Week 4)

- [ ] Update Mergify config: enable auto-merge for `github-actions` only
- [ ] Commit and deploy Mergify changes
- [ ] Wait for at least 1 GitHub Actions security PR to auto-merge
- [ ] Monitor for 1 week
- [ ] Document any issues or learnings
- [ ] Team retrospective: ready for full rollout?

### Phase 5: Full Rollout (Week 5)

- [ ] Update Mergify config: enable auto-merge for all ecosystems
- [ ] Commit and deploy Mergify changes
- [ ] Announce to team: auto-merge now active
- [ ] Monitor closely for 2 weeks (daily check-ins)
- [ ] Document any issues
- [ ] Weekly team check-ins

### Ongoing Operations

- [ ] Weekly: Review Mergify dashboard
- [ ] Monthly: Generate and review metrics
- [ ] Monthly: Clean up stale Dependabot PRs
- [ ] Quarterly: Full dependency audit
- [ ] Quarterly: Team retrospective on process
- [ ] As needed: Update ignored dependencies
- [ ] As needed: Adjust Mergify rules based on learnings

## Open Questions

1. **Test coverage threshold:** Current coverage is unknown. Need to verify > 70% before enabling auto-merge.

2. **Branch protection rules:** Are there existing branch protection rules that might conflict with Mergify? Need to audit.

3. **Deployment automation:** After auto-merge to main, how quickly does this deploy to production? Need to understand deployment pipeline.

4. **Notification preferences:** Should we set up Slack notifications for auto-merges? What channel?

5. **Emergency contacts:** Who should be notified if auto-merge causes production incident? Need on-call rotation.

## Alternatives Considered

### Alternative 1: GitHub Native Auto-Merge

**Approach:** Use GitHub's built-in auto-merge with Actions workflow

**Pros:**
- Free
- Native GitHub feature
- Simple setup

**Cons:**
- Less flexible rule configuration
- No analytics dashboard
- More Actions code to maintain
- Harder to set up complex conditions

**Decision:** Rejected in favor of Mergify for better features at low cost.

### Alternative 2: Renovate Bot

**Approach:** Use Renovate instead of Dependabot

**Pros:**
- More configuration options
- Better grouping of updates
- Supports more ecosystems

**Cons:**
- More complex setup
- Not native to GitHub
- Steeper learning curve
- Dependabot is "good enough"

**Decision:** Rejected. Dependabot is simpler and meets our needs.

### Alternative 3: Manual Process with Scheduled Reminders

**Approach:** Keep manual process, add calendar reminders to check for updates

**Pros:**
- Full human control
- No automation risk
- Zero cost

**Cons:**
- Slow CVE response (days/weeks)
- High manual toil
- Inconsistent execution
- Doesn't scale

**Decision:** Rejected. Does not meet goal of rapid CVE remediation.

## References

- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [Mergify Documentation](https://docs.mergify.com/)
- [GitHub Actions Auto-Merge](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)
- [pip-compile Documentation](https://github.com/jazzband/pip-tools)

## Appendix

### Example Dependabot PR

**Title:** `Bump django from 4.2.22 to 4.2.23`

**Labels:** `dependencies`, `python`, `security`

**Description:**
```
Bumps django from 4.2.22 to 4.2.23.

Release notes
Sourced from django's releases.

Django 4.2.23
Django 4.2.23 fixes a security issue with severity "high" in 4.2.22.

CVE-2024-XXXXX: Potential SQL injection in QuerySet.filter()
...

Commits
- abc1234 [4.2.x] Bumped version for 4.2.23 release.
- def5678 [4.2.x] Fixed CVE-2024-XXXXX -- ...

Dependabot compatibility score
Dependabot will resolve any conflicts with this PR as long as you don't alter it yourself.
```

### Example Mergify Auto-Merge

**Scenario:** Django security update PR created

**Timeline:**
1. **00:00** - Dependabot creates PR
2. **00:01** - `dependabot_pip_compile.yml` triggers
3. **00:03** - pip-compile completes, lockfiles committed
4. **00:04** - CI workflows trigger (pre-commit, pip_audit, pyright, selftest)
5. **00:15** - All CI checks pass (green)
6. **00:15** - Mergify evaluates conditions: ✅ All met
7. **00:15** - Mergify auto-merges PR
8. **00:16** - Branch deleted
9. **00:20** - Deployment pipeline deploys to production

**Total time:** 20 minutes from CVE fix to production

### Example Rollback

**Scenario:** Auto-merged Django update breaks user authentication

**Timeline:**
1. **10:00** - Production alert: authentication failures
2. **10:05** - Investigation identifies Django update as cause
3. **10:07** - Execute rollback:
   ```bash
   git revert abc1234
   git push origin main
   ```
4. **10:12** - Deployment pipeline deploys reverted version
5. **10:15** - Authentication restored
6. **10:30** - Pin Django version in `requirements.in`:
   ```python
   Django==4.2.22  # Pinned due to issue #1234 - auth regression
   ```
7. **10:35** - Create issue to investigate why tests didn't catch the bug
8. **Next week** - Add test coverage, remove pin, try update again

**Total downtime:** 15 minutes

## Conclusion

Enabling Dependabot and Mergify provides automated, rapid response to security vulnerabilities while maintaining developer control over feature updates. The phased rollout plan ensures safe adoption, and comprehensive monitoring enables continuous improvement. With proper test coverage and team buy-in, this system will significantly reduce CVE exposure while freeing developer time for feature work.

**Recommendation:** Proceed with implementation following the 5-week phased rollout plan outlined above.
