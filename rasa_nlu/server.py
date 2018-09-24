import argparse
import io
import logging
import os
from functools import wraps

import simplejson
from klein import Klein
from twisted.internet import reactor, threads
from twisted.internet.defer import inlineCallbacks, returnValue
from os.path import normpath, basename
import os

from rasa_nlu import config, utils
import rasa_nlu.cli.server as cli
from rasa_nlu.config import RasaNLUModelConfig
from rasa_nlu.data_router import (
    DataRouter, InvalidProjectError, MaxTrainingError)
from rasa_nlu.model import MINIMUM_COMPATIBLE_VERSION
from rasa_nlu.train import TrainingException
from rasa_nlu.utils import json_to_string, read_endpoints
from rasa_nlu.version import __version__

logger = logging.getLogger(__name__)


def create_argument_parser():
    parser = argparse.ArgumentParser(description='parse incoming text')
<<<<<<< HEAD
    cli.add_server_arguments(parser)
=======

    parser.add_argument('-e', '--emulate',
                        choices=['wit', 'luis', 'dialogflow'],
                        help='which service to emulate (default: None i.e. use'
                             ' simple built in format)')
    parser.add_argument('-P', '--port',
                        type=int,
                        default=5000,
                        help='port on which to run server')
    parser.add_argument('--pre_load',
                        nargs='+',
                        default=[],
                        help='Preload specific projects or models into memory '
                             'before starting the server. \nEg: python -m '
                             'rasa_nlu.server --pre_load projectX/'
                             'my_model_1 --pre_load projectY/my_model_2 '
                             '-c config.yaml')
    parser.add_argument('-t', '--token',
                        help="auth token. If set, reject requests which don't "
                             "provide this token as a query parameter")
    parser.add_argument('-w', '--write',
                        help='file where logs will be saved')
    parser.add_argument('--path',
                        required=True,
                        help="working directory of the server. Models are"
                             "loaded from this directory and trained models "
                             "will be saved here.")
    parser.add_argument('--cors',
                        nargs="*",
                        help='List of domain patterns from where CORS '
                             '(cross-origin resource sharing) calls are '
                             'allowed. The default value is `[]` which '
                             'forbids all CORS requests.')

    parser.add_argument('--max_training_processes',
                        type=int,
                        default=1,
                        help='Number of processes used to handle training '
                             'requests. Increasing this value will have a '
                             'great impact on memory usage. It is '
                             'recommended to keep the default value.')
    parser.add_argument('--num_threads',
                        type=int,
                        default=1,
                        help='Number of parallel threads to use for '
                             'handling parse requests.')
    parser.add_argument('--endpoints',
                        help='Configuration file for the model server '
                             'as a yaml file')
    parser.add_argument('--wait_time_between_pulls',
                        type=int,
                        default=10,
                        help='Wait time in seconds between NLU model server'
                             'queries.')
    parser.add_argument('--response_log',
                        help='Directory where logs will be saved '
                             '(containing queries and responses).'
                             'If set to ``null`` logging will be disabled.')
    parser.add_argument('--storage',
                        help='Set the remote location where models are stored. '
                             'E.g. on AWS. If nothing is configured, the '
                             'server will only serve the models that are '
                             'on disk in the configured `path`.')
    parser.add_argument('-c', '--config',
                        help="Default model configuration file used for "
                             "training.")

>>>>>>> dynamically load models with _pre_load_model
    utils.add_logging_option_arguments(parser)

    return parser


def check_cors(f):
    """Wraps a request handler with CORS headers checking."""

    @wraps(f)
    def decorated(*args, **kwargs):
        self = args[0]
        request = args[1]
        origin = request.getHeader('Origin')

        if origin:
            if '*' in self.cors_origins:
                request.setHeader('Access-Control-Allow-Origin', '*')
                request.setHeader(
                    'Access-Control-Allow-Headers', 'Content-Type')
                request.setHeader(
                    'Access-Control-Allow-Methods',
                    'POST, GET, OPTIONS, PUT, DELETE')
            elif origin in self.cors_origins:
                request.setHeader('Access-Control-Allow-Origin', origin)
                request.setHeader(
                    'Access-Control-Allow-Headers', 'Content-Type')
                request.setHeader(
                    'Access-Control-Allow-Methods',
                    'POST, GET, OPTIONS, PUT, DELETE')
            else:
                request.setResponseCode(403)
                return 'forbidden'

        if request.method.decode('utf-8', 'strict') == 'OPTIONS':
            return ''  # if this is an options call we skip running `f`
        else:
            return f(*args, **kwargs)

    return decorated


def requires_auth(f):
    """Wraps a request handler with token authentication."""

    @wraps(f)
    def decorated(*args, **kwargs):
        self = args[0]
        request = args[1]
        token = request.args.get(b'token', [b''])[0].decode("utf8")
        if self.access_token is None or token == self.access_token:
            return f(*args, **kwargs)
        request.setResponseCode(401)
        return 'unauthorized'

    return decorated


def decode_parameters(request):
    """Make sure all the parameters have the same encoding."""

    return {
        key.decode('utf-8', 'strict'): value[0].decode('utf-8', 'strict')
        for key, value in request.args.items()}


def parameter_or_default(request, name, default=None):
    """Return a parameters value if part of the request, or the default."""

    request_params = decode_parameters(request)
    return request_params.get(name, default)


def dump_to_data_file(data):
    if isinstance(data, str):
        data_string = data
    else:
        data_string = utils.json_to_string(data)

    return utils.create_temporary_file(data_string, "_training_data")


class RasaNLU(object):
    """Class representing Rasa NLU http server"""

    app = Klein()

    def __init__(self,
                 data_router,
                 loglevel='INFO',
                 logfile=None,
                 num_threads=1,
                 token=None,
                 cors_origins=None,
                 testing=False,
                 default_config_path=None):

        self._configure_logging(loglevel, logfile)

        self.default_model_config = self._load_default_config(
            default_config_path)

        self.data_router = data_router
        self._testing = testing
        self.cors_origins = cors_origins if cors_origins else ["*"]
        self.access_token = token
        reactor.suggestThreadPoolSize(num_threads * 5)

    @staticmethod
    def _load_default_config(path):
        if path:
            return config.load(path).as_dict()
        else:
            return {}

    @staticmethod
    def _configure_logging(loglevel, logfile):
        logging.basicConfig(filename=logfile,
                            level=loglevel)
        logging.captureWarnings(True)

    @app.route("/", methods=['GET', 'OPTIONS'])
    @check_cors
    def hello(self, request):
        """Main Rasa route to check if the server is online"""
        return "hello from Rasa NLU: " + __version__

    @app.route("/parse", methods=['GET', 'POST', 'OPTIONS'])
    @requires_auth
    @check_cors
    @inlineCallbacks
    def parse(self, request):
        request.setHeader('Content-Type', 'application/json')
        if request.method.decode('utf-8', 'strict') == 'GET':
            request_params = decode_parameters(request)
        else:
            request_params = simplejson.loads(
                request.content.read().decode('utf-8', 'strict'))

        if 'query' in request_params:
            request_params['q'] = request_params.pop('query')

        if 'q' not in request_params:
            request.setResponseCode(404)
            dumped = json_to_string(
                {"error": "Invalid parse parameter specified"})
            returnValue(dumped)
        else:
            data = self.data_router.extract(request_params)
            try:
                request.setResponseCode(200)
                response = yield (self.data_router.parse(data) if self._testing
                                  else threads.deferToThread(
                    self.data_router.parse, data))
                returnValue(json_to_string(response))
            except InvalidProjectError as e:
                request.setResponseCode(404)
                returnValue(json_to_string({"error": "{}".format(e)}))
            except Exception as e:
                request.setResponseCode(500)
                logger.exception(e)
                returnValue(json_to_string({"error": "{}".format(e)}))

    @app.route("/version", methods=['GET', 'OPTIONS'])
    @requires_auth
    @check_cors
    def version(self, request):
        """Returns the Rasa server's version"""

        request.setHeader('Content-Type', 'application/json')
        return json_to_string(
            {'version': __version__,
             'minimum_compatible_version': MINIMUM_COMPATIBLE_VERSION}
        )

    @app.route("/status", methods=['GET', 'OPTIONS'])
    @requires_auth
    @check_cors
    def status(self, request):
        request.setHeader('Content-Type', 'application/json')
        return json_to_string(self.data_router.get_status())

    def extract_json(self, content):
        # test if json has config structure
        json_config = simplejson.loads(content).get("data")

        # if it does then this results in correct format.
        if json_config:

            model_config = simplejson.loads(content)
            data = json_config

        # otherwise use defaults.
        else:

            model_config = self.default_model_config
            data = content

        return model_config, data

    def extract_data_and_config(self, request):

        request_content = request.content.read().decode('utf-8', 'strict')
        content_type = self.get_request_content_type(request)

        if 'yml' in content_type:
            # assumes the user submitted a model configuration with a data
            # parameter attached to it

            model_config = utils.read_yaml(request_content)
            data = model_config.get("data")

        elif 'json' in content_type:

            model_config, data = self.extract_json(request_content)

        else:

            raise Exception("Content-Type must be 'application/x-yml' "
                            "or 'application/json'")

        return model_config, data

    def get_request_content_type(self, request):
        content_type = request.requestHeaders.getRawHeaders("Content-Type", [])

        if len(content_type) is not 1:
            raise Exception("The request must have exactly one content type")
        else:
            return content_type[0]

    @app.route("/train", methods=['POST', 'OPTIONS'], branch=True)
    @requires_auth
    @check_cors
    @inlineCallbacks
    def train(self, request):
        # if not set will use the default project name, e.g. "default"
        project = parameter_or_default(request, "project", default=None)
        # if set will not generate a model name but use the passed one
        model_name = parameter_or_default(request, "model", default=None)

        try:
            model_config, data = self.extract_data_and_config(request)

        except Exception as e:
            request.setResponseCode(400)
            returnValue(json_to_string({"error": "{}".format(e)}))

        data_file = dump_to_data_file(data)

        request.setHeader('Content-Type', 'application/zip')

        try:
            request.setResponseCode(200)
            request.setHeader("Content-Disposition", "attachment")
            path_to_model = yield self.data_router.start_train_process(
                data_file, project,
                RasaNLUModelConfig(model_config), model_name)
            zipped_path = utils.zip_folder(path_to_model)

            zip_content = io.open(zipped_path, 'r+b').read()
            return returnValue(zip_content)

        except MaxTrainingError as e:
            request.setResponseCode(403)
            returnValue(json_to_string({"error": "{}".format(e)}))
        except InvalidProjectError as e:
            request.setResponseCode(404)
            returnValue(json_to_string({"error": "{}".format(e)}))
        except TrainingException as e:
            request.setResponseCode(500)
            returnValue(json_to_string({"error": "{}".format(e)}))

    @app.route("/evaluate", methods=['POST', 'OPTIONS'])
    @requires_auth
    @check_cors
    @inlineCallbacks
    def evaluate(self, request):
        data_string = request.content.read().decode('utf-8', 'strict')
        params = {
            key.decode('utf-8', 'strict'): value[0].decode('utf-8', 'strict')
            for key, value in request.args.items()
        }

        request.setHeader('Content-Type', 'application/json')

        try:
            request.setResponseCode(200)
            response = yield self.data_router.evaluate(data_string,
                                                       params.get('project'),
                                                       params.get('model'))
            returnValue(json_to_string(response))
        except Exception as e:
            request.setResponseCode(500)
            returnValue(json_to_string({"error": "{}".format(e)}))

    @app.route("/models", methods=['DELETE', 'OPTIONS'])
    @requires_auth
    @check_cors
    def unload_model(self, request):
        params = {
            key.decode('utf-8', 'strict'): value[0].decode('utf-8', 'strict')
            for key, value in request.args.items()
        }

        request.setHeader('Content-Type', 'application/json')
        try:
            request.setResponseCode(200)
            response = self.data_router.unload_model(
                params.get('project', RasaNLUModelConfig.DEFAULT_PROJECT_NAME),
                params.get('model')
            )
            return simplejson.dumps(response)
        except Exception as e:
            request.setResponseCode(500)
            logger.exception(e)
            return simplejson.dumps({"error": "{}".format(e)})


<<<<<<< HEAD
def get_token(_clitoken: str) -> str:
    _envtoken = os.environ.get("RASA_NLU_TOKEN")

    if _clitoken and _envtoken:
        raise Exception(
            "RASA_NLU_TOKEN is set both with the -t option,"
            " with value `{}`, and with an environment variable, "
            "with value `{}`. "
            "Please set the token with just one method "
            "to avoid unexpected behaviours.".format(
                _clitoken, _envtoken))

    token = _clitoken or _envtoken
    return token

def get_absolute_path(model_path, current_path):
    model_path = model_path.rstrip("/")
    current_path = current_path.rstrip("/")
    if not current_path.startswith('/'):
        current_path = '/' + current_path
    if(model_path.startswith('/')):
        return model_path
    else:
        return current_path + "/" + model_path


def parse_model(path):
    project, model = filter(None, path.split('/')[-2:])
    return (project, model)


def parse_project(path):
    project = path.split('/')[-1]
    return project


def parse_pre_load_path(pre_load_path):
    pre_load_path_split = pre_load_path.lstrip("/").split('/')
    is_potential_model_or_project_path = len(pre_load_path_split) > 1
    is_potential_project_path = len(pre_load_path_split) > 0
    return (
        pre_load_path_split,
        is_potential_model_or_project_path,
        is_potential_project_path
    )

def should_fetch_from_cloud(
    is_local_model,
    is_local_project,
    is_potential_model_or_project_path):
    return (
        not is_local_model and
        not is_local_project and
        is_potential_model_or_project_path
    )


def parse_project_and_model(
        is_local_model,
        is_local_project,
        pre_load_path,
        absolute_path):

    (
        pre_load_path_split,
        is_potential_model_or_project_path,
        is_potential_project_path
    ) = parse_pre_load_path(pre_load_path)

    result = []
    if is_local_model:
        # the argument is a model
        project, model = parse_model(pre_load_path)
        result = result + (project, model, absolute_path)

    elif is_local_project or is_potential_project_path:
        # the argument is a project
        project = parse_project(pre_load_path)
        result = result + (project, None, absolute_path)

    if should_fetch_from_cloud(
        is_local_model,
        is_local_project,
        is_potential_model_or_project_path):
        # if we did not find anything locally,
        # we can assume the project or model is stored on the cloud
        # we do not know yet if it is a project or a model,
        # so we try to load both
        result = result + [
            (project, model, absolute_path),
            (model, None, absolute_path)
        ]
    return result


def parse_pre_load(pre_load_args, path):
    parsed_results = []
    for pre_load_path in pre_load_args:

        pre_load_path = pre_load_path.rstrip("/")
        absolute_path = get_absolute_path(pre_load_path, path)

        is_local_model = os.path.isfile(absolute_path + '/metadata.json')
        is_local_project = os.path.isdir(pre_load_path)

        parsed_projects_and_models = parse_project_and_model(
            is_local_model,
            is_local_project,
            pre_load_path,
            absolute_path
        )
        if len(parsed_projects_and_models) == 0:
            logger.error('invalid input')
        parsed_results = parsed_results + parsed_projects_and_models

    return parsed_results



def main(args):
    utils.configure_colored_logging(args.loglevel)
    pre_load = args.pre_load
    _endpoints = read_endpoints(args.endpoints)

    router = DataRouter(
        args.path,
        args.max_training_processes,
        args.response_log,
        args.emulate,
        args.storage,
        model_server=_endpoints.model,
        wait_time_between_pulls=args.wait_time_between_pulls
    )

    if pre_load:
        logger.debug('Preloading....')
        parsed_input = parse_pre_load(pre_load, cmdline_args.path)
        for (project, model, absolute_path) in parsed_input:
            router._pre_load(project, model, absolute_path)

    rasa = RasaNLU(
        router,
        args.loglevel,
        args.write,
        args.num_threads,
        get_token(cmdline_args.token),
        args.cors,
        default_config_path=args.config
    )

    logger.info('Started http server on port %s' % args.port)
    rasa.app.run('0.0.0.0', args.port)


if __name__ == '__main__':
    # Running as standalone python application
    cmdline_args = create_argument_parser().parse_args()
    main(cmdline_args)
