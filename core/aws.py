"""One AWS session for the whole process.

Locally this is the `ninja` profile. In Lambda there are no profiles at all, and asking for
one raises `ProfileNotFound` before a single line of business logic runs. So the profile is
used only when it is both configured and actually present on the machine.
"""

from __future__ import annotations

import os
from functools import lru_cache

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")


DEFAULT_PROFILE = "ninja"


def in_lambda() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


@lru_cache(maxsize=1)
def session() -> boto3.Session:
    if in_lambda():
        return boto3.Session(region_name=REGION)
    profile = os.environ.get("AWS_PROFILE") or DEFAULT_PROFILE
    if profile in boto3.Session().available_profiles:
        return boto3.Session(profile_name=profile, region_name=REGION)
    return boto3.Session(region_name=REGION)
