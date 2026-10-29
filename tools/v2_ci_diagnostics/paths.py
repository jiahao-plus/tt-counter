"""paths.py -- where the diagnostic scripts find the CI run and this repo.

The third-round run artefacts are NOT committed (they are large, and the user
explicitly excluded historical log archives).  Point the scripts at them with
two environment variables instead of baking someone's home directory into the
source:

    TT_RUN_DIR   the LibreLane run directory, i.e. the one containing
                 `final/`, `18-openroad-cutrows/`, `62-magic-drc/`, ...
                 default: <lesson>/GDS_logs/runs/wokwi, where <lesson> is the
                 directory that holds this repo (`tt-v2`)
    TT_REPO      this repository's working tree
                 default: the parent of this script's directory

Both fall back to the conventional layout, so on the original machine the
scripts run with no environment at all.  Nothing here is machine-specific once
the two variables are set.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

# <repo>/tools/v2_ci_diagnostics  ->  <repo>
REPO = os.path.abspath(os.environ.get(
    'TT_REPO', os.path.dirname(os.path.dirname(_HERE))))

# <lesson>/GDS_logs/runs/wokwi, where <lesson> holds this repo as a subdirectory
# (tt-v2 sits next to GDS_logs under the same parent).
RUN = os.path.abspath(os.environ.get(
    'TT_RUN_DIR',
    os.path.join(os.path.dirname(os.path.dirname(REPO)),
                 'GDS_logs', 'runs', 'wokwi')))

# The older scripts name these two differently.  Keep both spellings so the
# individual diagnostics can be read without cross-referencing this file.
BASE = RUN
TT = REPO


def describe():
    """One-line provenance banner the scripts print at start-up."""
    return 'repo=%s\nrun =%s' % (REPO, RUN)
