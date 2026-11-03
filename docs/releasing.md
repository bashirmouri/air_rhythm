# Releasing a new version

GitHub builds, tests and drafts every release on a fresh Windows machine
(`.github/workflows/release.yml`). Nothing is public until you publish the draft.

1. **Set the version** in `src/air_rhythm/__init__.py` (`__version__ = "0.2.0"`).
2. **Update `CHANGELOG.md`:** rename `## [Unreleased]` to `## [0.2.0] - <date>`, and add a new,
   empty `## [Unreleased]` above it. That section becomes the release notes.
3. **Commit, tag and push:**
   ```bash
   git commit -am "Release 0.2.0"
   git tag v0.2.0
   git push origin main v0.2.0
   ```
4. **Follow it** in the repo's **Actions** tab (a few minutes). It checks that the tag matches
   the version and that the changelog has a section for it, runs the tests, builds the game,
   starts the built game to check it works, and creates a **draft** release with the zip and notes.
5. **Open Releases**, check the draft (notes, zip size), and click **Publish release**.

If a check fails, nothing is released: fix it, delete the tag (`git tag -d v0.2.0` and
`git push origin :refs/tags/v0.2.0`), and tag again.

## Test run without releasing

**Actions → Release → Run workflow** runs the same build and checks, but only keeps the zip
as a download on the run's page (30 days); no release is created.

## Notes

- The zip's checksum changes with every build (file timestamps), even for the same code.
  The release notes quote the right one automatically.
- Version numbers follow [Semantic Versioning](https://semver.org/): fixes bump the last
  number (0.2.**1**), new features the middle one (0.**3**.0).
- Players update by downloading the new zip and replacing the folder; their settings stay
  in their data folder. The game never checks for updates by itself (it stays offline).
