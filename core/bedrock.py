"""Bedrock model construction.

Two models, chosen for the job rather than uniformly:

* Intake is mechanical extraction at high volume — Claude Haiku 4.5.
* Reasoning about whether a person has stopped being themselves is a judgment call, and
  the cost of a false negative is a missed infection — Claude Opus 5.

Bedrock refuses the bare model ids for these models with a `ValidationException`; they are
only invocable through an inference profile, hence the `us.` prefix.
"""

from __future__ import annotations

import os

import boto3
from strands.models import BedrockModel

REGION = os.environ.get("AWS_REGION", "us-west-2")
PROFILE = os.environ.get("AWS_PROFILE", "ninja")

INTAKE_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_INTAKE", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
REASONING_MODEL_ID = os.environ.get("BEDROCK_MODEL_REASONING", "us.anthropic.claude-opus-5")


def _session() -> boto3.Session:
    return boto3.Session(profile_name=PROFILE, region_name=REGION)


def intake_model(**overrides) -> BedrockModel:
    return BedrockModel(
        boto_session=_session(),
        model_id=INTAKE_MODEL_ID,
        max_tokens=2000,
        **overrides,
    )


def reasoning_model(**overrides) -> BedrockModel:
    return BedrockModel(
        boto_session=_session(),
        model_id=REASONING_MODEL_ID,
        max_tokens=4000,
        **overrides,
    )
