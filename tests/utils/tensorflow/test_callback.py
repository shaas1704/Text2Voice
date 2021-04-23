from typing import Dict, Text, List
from pathlib import Path

import pytest
import sys

from rasa.core.agent import Agent
from rasa.core.policies.ted_policy import TEDPolicy
from rasa.utils.tensorflow.callback import RasaModelCheckpoint

BOTH_IMPROVED = [
    {"val_i_acc": 0.5, "val_f1": 0.5},
    {"val_i_acc": 0.7, "val_f1": 0.7}
]
ONE_IMPROVED_ONE_EQUAL = [
    {"val_i_acc": 0.5, "val_f1": 0.5},
    {"val_i_acc": 0.5, "val_f1": 0.7},
]
BOTH_EQUAL = [
    {"val_i_acc": 0.7, "val_f1": 0.7},
    {"val_i_acc": 0.7, "val_f1": 0.7}
]
ONE_IMPROVED_ONE_WORSE = [
    {"val_i_acc": 0.6, "val_f1": 0.5},
    {"val_i_acc": 0.4, "val_f1": 0.7},
]
ONE_WORSE_ONE_EQUAL = [
    {"val_i_acc": 0.7, "val_f1": 0.5},
    {"val_i_acc": 0.5, "val_f1": 0.5},
]


@pytest.mark.parametrize(
    "logs, improved",
    [
        (BOTH_IMPROVED, True),
        (ONE_IMPROVED_ONE_EQUAL, True),
        (BOTH_EQUAL, False),
        (ONE_IMPROVED_ONE_WORSE, False),
        (ONE_WORSE_ONE_EQUAL, False),
    ],
)
def test_does_model_improve(logs: List[Dict[Text, float]], improved, tmpdir: Path):
    checkpoint = RasaModelCheckpoint(tmpdir)
    checkpoint.best_metrics_so_far = logs[0]
    # true iff all values are equal or better and at least one is better
    assert checkpoint._does_model_improve(logs[1]) == improved


@pytest.fixture(scope="session")
def trained_ted(mood_agent: Agent) -> TEDPolicy:
    # use the moodbot agent to get a trained TEDPolicy
    for policy in mood_agent.policy_ensemble.policies:
        if isinstance(policy, TEDPolicy):
            return policy


@pytest.mark.parametrize(
    "logs, improved",
    [
        ([{"val_i_acc": 0.5, "val_f1": 0.5}, {"val_i_acc": 0.5, "val_f1": 0.7}], True),
        ([{"val_i_acc": 0.5, "val_f1": 0.5}, {"val_i_acc": 0.4, "val_f1": 0.5}], False)
    ]
)
def test_on_epoch_end_saves_checkpoints_file(
    logs: List[Dict[Text, float]], improved: bool, trained_ted: TEDPolicy, tmpdir: Path
):
    for log in logs:
        sys.stdout.write("[")
        for k, v in log.items():
            sys.stdout.write(f"{k}:{v} ")
        sys.stdout.write("] ")
    sys.stdout.write("\n")
    model_name = "checkpoint"
    best_model_file = Path(str(tmpdir), model_name)
    assert not best_model_file.exists()
    checkpoint = RasaModelCheckpoint(tmpdir)
    checkpoint.best_metrics_so_far = logs[0]
    checkpoint.model = trained_ted.model
    checkpoint.on_epoch_end(1, logs[1])
    if improved:
        assert best_model_file.exists()
    else:
        assert not best_model_file.exists()
