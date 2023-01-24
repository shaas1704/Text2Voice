import os

TEST_DATA_FILE = "test.yml"
TRAIN_DATA_FILE = "train.yml"
NLG_DATA_FILE = "responses.yml"
RESULTS_FILE = "results.json"
NUMBER_OF_TRAINING_STORIES_FILE = "num_stories.json"
PERCENTAGE_KEY = "__percentage__"

PACKAGE_NAME = "rasa"

DEFAULT_RASA_PORT = 5005

# Key in global config file which contains whether the user agreed to telemetry
# reporting. These are reused in Rasa X. Keep this in mind when changing their names.
CONFIG_FILE_TELEMETRY_KEY = "metrics"
CONFIG_TELEMETRY_ID = "rasa_user_id"
CONFIG_TELEMETRY_ENABLED = "enabled"
CONFIG_TELEMETRY_DATE = "date"

MINIMUM_COMPATIBLE_VERSION = "3.0.0"

GLOBAL_USER_CONFIG_PATH = os.path.expanduser("~/.config/rasa/global.yml")

DEFAULT_LOG_LEVEL_LIBRARIES = "ERROR"
ENV_LOG_LEVEL_LIBRARIES = "LOG_LEVEL_LIBRARIES"
ENV_LOG_LEVEL_MATPLOTLIB = "LOG_LEVEL_MATPLOTLIB"
ENV_LOG_LEVEL_RABBITMQ = "LOG_LEVEL_RABBITMQ"
ENV_LOG_LEVEL_KAFKA = "LOG_LEVEL_KAFKA"

DEFAULT_SANIC_WORKERS = 1
ENV_SANIC_WORKERS = "SANIC_WORKERS"
ENV_SANIC_BACKLOG = "SANIC_BACKLOG"

ENV_GPU_CONFIG = "TF_GPU_MEMORY_ALLOC"
ENV_CPU_INTER_OP_CONFIG = "TF_INTER_OP_PARALLELISM_THREADS"
ENV_CPU_INTRA_OP_CONFIG = "TF_INTRA_OP_PARALLELISM_THREADS"

ENV_ACTION_OMIT_DOMAIN = "ACTION_OMIT_DOMAIN"
