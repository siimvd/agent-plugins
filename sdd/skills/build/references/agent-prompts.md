# Subagent Prompt Templates

Prompt templates for short-lived subagents spawned during the build phase.

## Investigation Subagent (Explore)

Spawn before implementing a task that touches unfamiliar code.

```
Research this part of the codebase to prepare for implementation.
DO NOT write any files. Read and search only.

**Task context**: [paste task description from spec]
**Files to investigate**: [paste file paths from task]

**Questions**:
1. What patterns does the existing code follow?
2. Are there hidden dependencies or complexity?
3. What's the best integration point?
4. Are there existing tests that show expected behavior?

Return:
- Key findings (with exact file paths and line numbers)
- Patterns to follow
- Gotchas or hidden complexity
- Recommended implementation approach
```

## Code Review Subagent

Spawn after implementing a task that triggers an adaptive review.

```
Review the changes for this task against the spec.

**Spec requirements for this task**:
[paste task section from spec including acceptance criteria]

**Changes to review**:
[paste output of: git diff HEAD~1]

Check for:
- Spec compliance — does the implementation match all acceptance criteria?
- Logic errors — incorrect conditions, off-by-one, null handling
- Missing error handling at system boundaries (user input, external APIs)
- Naming consistency with existing codebase patterns
- Test coverage gaps — are all acceptance criteria tested?

Report only issues with HIGH confidence. Skip style and formatting.
If no high-confidence issues found, say "No issues found."
```

## Code Simplifier Subagent

Spawn once at the end (Phase 4a), before PR goes to ready.

```
Review all files changed in this branch compared to main.
Simplify code while preserving ALL existing functionality and tests.

Files to review:
[paste output of: git diff --name-only main...HEAD]

Focus on:
- Reducing nesting and cyclomatic complexity
- Eliminating redundant code or duplicate logic
- Improving variable and function naming for clarity
- Removing dead code or unused imports
- Following project conventions from CLAUDE.md
- Preferring explicit code over clever/compact solutions

DO NOT:
- Add new features or functionality
- Change public APIs or function signatures
- Create abstractions for one-time operations
- Add comments to code that is already clear
- Over-simplify (three similar lines > premature abstraction)

Make the changes directly. Run tests after to verify nothing broke.
```

## Security Review Subagent

Spawn once at the end (Phase 4b), before PR goes to ready.

```
Security review of all files changed in this branch.

Files to review:
[paste output of: git diff --name-only main...HEAD]

Check for OWASP Top 10 vulnerabilities:
- Injection (SQL, XSS, command injection, path traversal)
- Broken authentication or authorization
- Sensitive data exposure (API responses, logs, error messages)
- Security misconfiguration (insecure defaults, missing headers)
- Hardcoded secrets, API keys, or credentials
- Missing input validation at system boundaries
- Insecure deserialization
- Missing rate limiting on new endpoints

Report only HIGH and CRITICAL severity issues.
For each issue, provide:
- File and line number
- Severity (HIGH or CRITICAL)
- Description of the vulnerability
- Recommended fix

If no high-severity issues found, say "No security issues found."
```

## Migration Analysis Subagent

Spawn when a task creates or modifies database migrations.

```
Analyze this database migration for safety.

**Migration file**: [path to migration]
**Migration SQL**:
[paste migration content]

Check for:
- Is this migration reversible? If not, is that acceptable?
- Will it lock tables on large datasets? For how long?
- Are there data loss risks (dropping columns, changing types)?
- Is there a safe rollback strategy?
- Are default values set for new non-nullable columns?
- Does it need to run in a transaction?
- Is there a dependency on application code changes?

Recommend:
- Any changes to make the migration safer
- Whether to split into multiple migrations
- A rollback plan
```

## Task Implementation Subagent (--isolated-tasks mode)

Spawn per task when `--isolated-tasks` is specified. Each gets a clean context.

```
Implement a single task from the spec below.

## Full Spec
[paste entire spec file content]

## Your Task
[paste the specific task section]

## Implementation Notes
[paste the Implementation Notes section from spec]

## Instructions
1. Read the reference files listed in your task
2. Write tests first (TDD) — cover all acceptance criteria
3. Implement the minimal code to pass tests
4. Follow patterns from reference files exactly
5. Run tests: [test command from Implementation Notes]
6. Run lint: [lint command from Implementation Notes]
7. Fix any failures
8. Stage only files related to this task (not git add .)
9. Commit with the message specified in the task
10. Terminate — do not continue to other tasks

DO NOT:
- Implement other tasks
- Modify files not listed in your task
- Change the spec file
- Skip tests
```
