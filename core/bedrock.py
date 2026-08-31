"""Bedrock model construction.

Two models, chosen for the job rather than uniformly:

* Intake is mechanical extraction at high volume — Claude Haiku 4.5.
* Reasoning about whether a person has stopped being themselves is a judgment call, and
  the cost of a false negative is a missed infection — Claude Opus 5.

Bedrock refuses the bare model ids for these models with a `ValidationException`; they are
only invocable through an inference profile, hence the `us.` prefix.

These models are served through AWS Marketplace, so an account needs three separate things
before they answer, and none of them implies the others: the Anthropic use-case form, a
valid payment instrument, and an accepted model agreement per model
(`bedrock create-foundation-model-agreement`). Missing any one of them returns
`AccessDeniedException: INVALID_PAYMENT_INSTRUMENT`, which names only the second.

Note on `max_tokens`: thinking is on by default for Claude Opus 5, and the budget covers
thinking *and* the response together. This does not fail loudly. At 8000 the watch agent
reliably thought, wrote "I'll sweep now", and ended its turn having called no tools — a
plausible-looking answer that did nothing. At 32000 the same code works every time. When an
agent on this model appears lazy, suspect the budget before the prompt.
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
    config = {"model_id": INTAKE_MODEL_ID, "max_tokens": 2000} | overrides
    return BedrockModel(boto_session=_session(), **config)


def reasoning_model(**overrides) -> BedrockModel:
    config = {"model_id": REASONING_MODEL_ID, "max_tokens": 32000} | overrides
    return BedrockModel(boto_session=_session(), **config)
