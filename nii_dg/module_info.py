#!/usr/bin/env python3
# coding: utf-8

"""
Configuration parameters for the nii_dg package.
"""

GH_REPO: str = "ivis-tsukioka/nii-dg-fork"
"""str: The GitHub repository name for the nii_dg package."""

GH_REF: str = "demo-myschema-01"
"""str: The GitHub reference (tag or branch) for the nii_dg package."""


if __name__ == "__main__":
    print(GH_REF, end="")
