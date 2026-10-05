# Skills Manager management skill example

This is an opt-in example. It ships inside the Python package (and therefore
inside the sdist and wheel) so an installed distribution still carries it, but
it is never copied into an agent scope automatically.

Validate it from the repository root:

```sh
python3 -m skillsmgr validate --path skillsmgr/examples/skills-manager-management --json
```

After installing the distribution, the same file is available next to the
package (use `python3 -c "import skillsmgr, pathlib; print(pathlib.Path(skillsmgr.__file__).parent)"`):

```text
<site-packages>/skillsmgr/examples/skills-manager-management/SKILL.md
```

The portable skill instructions and explicit manual install/removal steps are
in [SKILL.md](SKILL.md). Review the whole file before installing it into one
user-selected scope.
