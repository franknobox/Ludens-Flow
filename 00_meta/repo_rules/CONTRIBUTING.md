# Contributing

Ludens-Flow is still moving quickly. Keep contributions focused, easy to review, and explicit about risk.

## Basic Rules

- Open a short-lived branch for each independent task.
- Keep one PR focused on one coherent change.
- Use English for commit and PR titles.
- PR descriptions can be written in Chinese.
- Add or update tests when behavior changes.
- Do not commit `.env`, API keys, local workspace data, logs, or private project files.

## Local Verification

Run these before opening a PR when relevant:

```bash
python -m unittest discover -s agent_workbench/tests
```

```bash
cd agent_workbench/web
npm run build
```

## PR Checklist

- [ ] I reviewed my diff.
- [ ] I removed unrelated changes and debug output.
- [ ] I documented manual verification if UI behavior changed.
- [ ] I did not include secrets or private workspace data.
