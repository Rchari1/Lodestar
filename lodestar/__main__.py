import sys

from lodestar.cli import main

# The guard matters: strategy code runs in "spawn" child processes, which
# re-import the parent's main module.
if __name__ == "__main__":
    sys.exit(main())
