---
name: save-version
description: "Use when the user says 'save this version', 'let's save', 'lock this down', 'commit this', 'tag this version', or 'push to github'. Runs the full release workflow: updates VERSION.txt and CHANGELOG.md, commits all changes, creates a git tag, and pushes everything to GitHub."
---

The user wants to save and publish the current state of the project as a named version. Execute the full release workflow below without stopping to ask questions — infer any missing information from VERSION.txt and CHANGELOG.md.

## Workflow

### Step 1 — Determine the version number
- If the user specified a version number, use that.
- Otherwise, read VERSION.txt to find the current version, then increment it appropriately based on the scope of changes (bug fix → patch, new feature → minor, breaking → major).

### Step 2 — Update VERSION.txt
- Set the version number to the new version.
- Set the release date to today's date.
- Write a one-line summary of what changed in this version.

### Step 3 — Update CHANGELOG.md
- Prepend a new `## [X.Y.Z] - YYYY-MM-DD` section at the top (below the header).
- Under `### Added`, `### Fixed`, `### Changed` headings, list every significant change made since the last version. Be specific — reference file names, bug descriptions, and what the fix was.
- Separate the new section from the previous one with `---`.

### Step 4 — Stage, commit, tag, and push
Run these commands in the terminal from the project root (`c:\Users\Dave\Desktop\ALAIRO\MedCast\medcast-deployment\carestream`):

```
git add -A
git commit -m "v{VERSION} - {ONE_LINE_SUMMARY}"
git tag v{VERSION}
git push origin main
git push origin --tags
```

### Step 5 — Confirm
Report back:
- The version number that was saved
- The GitHub URL of the commit (inferred from the remote: https://github.com/davidgorley/carestream)
- Confirm the tag was pushed
