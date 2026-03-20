# TODO

- [ ] Add tests
- [ ] Dedupe logic should account for content already in target repos (currently only checks source files against each other)
- [ ] Make dedupe check opt-in instead of opt-out
- [ ] Ignore empty files
- [ ] Create an AI tool Skill for populating the config file — should prompt user for enough information to generate a `mmm.yaml` config
- [ ] Make it easy to run from any directory — should work when `mmm.yaml` is in the cwd, without needing to be in the mmm source directory
- [ ] Add `diff` capability — show what would change in target repos before deploying
- [ ] Add `status` capability — diff current canonical source of truth against what's deployed and explain the differences (i.e. what has drifted since last deploy)
- [ ] Skip deployment to a tool if that tool isn't installed
- [ ] Support glob patterns in config — e.g. `my-skills/*` means copy all skills in that directory to targets
