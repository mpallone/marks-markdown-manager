# TODO

- [x] Add tests
- [x] Ignore empty files
- [ ] Make sure all features are documented in the README. Looks like 'diff' is missing. Also include `make` commands
- [ ] Update `make clean` to leave the mock-target folder structure alone, but delete any files that were used for testing 
- [ ] Create an AI tool Skill for populating the config file — should prompt user for enough information to generate a `mmm.yaml` config
- [ ] Prune stale symlinks when a skill/subagent source is removed (`status` flags them as BROKEN today, but nothing cleans them up)
- [ ] Friendly error when a configured `skills_dir`/`subagents_dir` exists as a regular file or dangling symlink (today `mkdir` raises a raw `FileExistsError` mid-deploy; predates the symlink refactor)
- [ ] Skip deployment to a tool if that tool isn't installed
- [ ] Support disabling a tool in the config — skip deployment to that tool without removing it from the config
- [ ] Support glob patterns in config — e.g. `my-skills/*` means deploy all skills in that directory to targets
- [ ] add docstrings everywhere
- [ ] build up my own confidence in the tool
- [ ] set up a few tools on my local machine so I can test manually
