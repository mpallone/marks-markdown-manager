# TODO

- [x] Add tests
- [x] Ignore empty files
- [ ] Create an AI tool Skill for populating the config file — should prompt user for enough information to generate a `mmm.yaml` config
- [x] Make it easy to run from any directory — should work when `mmm.yaml` is in the cwd, without needing to be in the mmm source directory
- [x] Add `diff` capability — show what would change in target repos before deploying
- [x] Add `status` capability — diff current canonical source of truth against what's deployed and explain the differences (i.e. what has drifted since last deploy)
- [x] Detect if there are no differences between source and target — make that clear to the user and skip copying
- [x] Skip deployment to a tool if that tool isn't installed
- [ ] Support disabling a tool in the config — skip deployment to that tool without removing it from the config
- [ ] Support glob patterns in config — e.g. `my-skills/*` means copy all skills in that directory to targets