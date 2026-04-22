# /test-merge

## Description
Dry-run merge a branch into the current branch and report conflict difficulty and resolution strategy.

## Usage
```
/test-merge <branch-name>
```

## Examples
```
/test-merge feature/soft-body-physics
```

## Steps

1. Save the current branch name and ensure the working tree is clean. If there are unstaged changes, abort and warn the user.
2. Run `git merge --no-commit --no-ff <branch-name>`.
3. If the merge is clean:
   - Report: "Clean merge. Run `git merge <branch-name>` to apply."
   - List the changed files.
   - Suggest running `PYTHONPATH=src pytest tests/ -q` before committing.
4. If there are conflicts:
   - For each conflicted file, classify the conflict difficulty:
     - **Easy**: Only new test classes added at the end of the file (no overlapping line edits).
     - **Medium**: Overlapping imports or configuration blocks.
     - **Hard**: Logic changes in the same function or method body.
   - For test files specifically, check if the conflict is just class-name overlap or import ordering.
5. Output:
   - Clean vs conflicted status
   - Per-file conflict difficulty
   - Suggested resolution strategy (e.g., "Accept both additions in test file", "Manual review required in scene_builder.py")
   - Post-resolution command: `PYTHONPATH=src pytest tests/ -q`
6. Always abort the dry-run merge with `git merge --abort` before finishing, unless the user explicitly asks to keep it.

## Rules
- Never leave the repo in a conflicted state after the skill finishes.
- If the branch does not exist, report it immediately.
- If the merge would delete files the user recently modified on main, flag as HIGH risk.
