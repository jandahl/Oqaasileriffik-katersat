#!/usr/bin/env python3
# Copyright 2024 Oqaasileriffik <oqaasileriffik@oqaasileriffik.gl>
# Licensed under the GNU GPL v3 or later - https://www.gnu.org/licenses/gpl-3.0.en.html

"""Write GitHub Actions step outputs (the GITHUB_OUTPUT file protocol)."""

import os


def set_output(name: str, value: str) -> None:
    """Write a `name=value` step output, if running under GitHub Actions.

    No-op when GITHUB_OUTPUT is unset, so callers still run standalone
    (locally, or outside Actions) without needing a fake environment.
    """
    path = os.environ.get('GITHUB_OUTPUT')
    if not path:
        return
    with open(path, 'a', encoding='utf-8') as f:
        f.write(f'{name}={value}\n')
