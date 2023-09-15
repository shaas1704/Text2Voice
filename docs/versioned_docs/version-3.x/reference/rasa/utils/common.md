---
sidebar_label: rasa.utils.common
title: rasa.utils.common
---
## TempDirectoryPath Objects

```python
class TempDirectoryPath(str, ContextManager)
```

Represents a path to an temporary directory.

When used as a context manager, it erases the contents of the directory on exit.

#### get\_temp\_dir\_name

```python
def get_temp_dir_name() -> Text
```

Returns the path name of a newly created temporary directory.

#### decode\_bytes

```python
def decode_bytes(name: Union[Text, bytes]) -> Text
```

Converts bytes object to string.

#### read\_global\_config

```python
def read_global_config(path: Text) -> Dict[Text, Any]
```

Read global Rasa configuration.

**Arguments**:

- `path` - Path to the configuration

**Returns**:

  The global configuration

#### configure\_logging\_from\_file

```python
def configure_logging_from_file(logging_config_file: Text) -> None
```

Parses YAML file content to configure logging.

**Arguments**:

- `logging_config_file` - YAML file containing logging configuration to handle
  custom formatting

#### configure\_logging\_and\_warnings

```python
def configure_logging_and_warnings(log_level: Optional[int] = None,
                                   logging_config_file: Optional[Text] = None,
                                   warn_only_once: bool = True,
                                   filter_repeated_logs: bool = True) -> None
```

Sets log levels of various loggers and sets up filters for warnings and logs.

**Arguments**:

- `log_level` - The log level to be used for the &#x27;Rasa&#x27; logger. Pass `None` to use
  either the environment variable &#x27;LOG_LEVEL&#x27; if it is specified, or the
  default log level otherwise.
- `logging_config_file` - YAML file containing logging configuration to handle
  custom formatting
- `warn_only_once` - determines whether user warnings should be filtered by the
  `warnings` module to appear only &quot;once&quot;
- `filter_repeated_logs` - determines whether `RepeatedLogFilter`s are added to
  the handlers of the root logger

#### configure\_library\_logging

```python
def configure_library_logging() -> None
```

Configures log levels of used libraries such as kafka, matplotlib, pika.

#### update\_apscheduler\_log\_level

```python
def update_apscheduler_log_level() -> None
```

Configures the log level of `apscheduler.*` loggers.

#### update\_socketio\_log\_level

```python
def update_socketio_log_level() -> None
```

Set the log level of socketio.

#### update\_tensorflow\_log\_level

```python
def update_tensorflow_log_level() -> None
```

Sets Tensorflow log level based on env variable &#x27;LOG_LEVEL_LIBRARIES&#x27;.

#### update\_sanic\_log\_level

```python
def update_sanic_log_level(log_file: Optional[Text] = None,
                           use_syslog: Optional[bool] = False,
                           syslog_address: Optional[Text] = None,
                           syslog_port: Optional[int] = None,
                           syslog_protocol: Optional[Text] = None) -> None
```

Set the log level to &#x27;LOG_LEVEL_LIBRARIES&#x27; environment variable .

#### update\_asyncio\_log\_level

```python
def update_asyncio_log_level() -> None
```

Set the log level of asyncio to the log level.

Uses the log level specified in the environment variable &#x27;LOG_LEVEL_LIBRARIES&#x27;.

#### update\_matplotlib\_log\_level

```python
def update_matplotlib_log_level(library_log_level: Text) -> None
```

Set the log level of matplotlib.

Uses the library specific log level or the general libraries log level.

#### update\_kafka\_log\_level

```python
def update_kafka_log_level(library_log_level: Text) -> None
```

Set the log level of kafka.

Uses the library specific log level or the general libraries log level.

#### update\_rabbitmq\_log\_level

```python
def update_rabbitmq_log_level(library_log_level: Text) -> None
```

Set the log level of pika.

Uses the library specific log level or the general libraries log level.

#### sort\_list\_of\_dicts\_by\_first\_key

```python
def sort_list_of_dicts_by_first_key(dicts: List[Dict]) -> List[Dict]
```

Sorts a list of dictionaries by their first key.

#### write\_global\_config\_value

```python
def write_global_config_value(name: Text, value: Any) -> bool
```

Read global Rasa configuration.

**Arguments**:

- `name` - Name of the configuration key
- `value` - Value the configuration key should be set to
  

**Returns**:

  `True` if the operation was successful.

#### read\_global\_config\_value

```python
def read_global_config_value(name: Text, unavailable_ok: bool = True) -> Any
```

Read a value from the global Rasa configuration.

#### update\_existing\_keys

```python
def update_existing_keys(original: Dict[Any, Any],
                         updates: Dict[Any, Any]) -> Dict[Any, Any]
```

Iterate through all the updates and update a value in the original dictionary.

If the updates contain a key that is not present in the original dict, it will
be ignored.

#### override\_defaults

```python
def override_defaults(defaults: Optional[Dict[Text, Any]],
                      custom: Optional[Dict[Text, Any]]) -> Dict[Text, Any]
```

Override default config with the given config.

We cannot use `dict.update` method because configs contain nested dicts.

**Arguments**:

- `defaults` - default config
- `custom` - user config containing new parameters
  

**Returns**:

  updated config

## RepeatedLogFilter Objects

```python
class RepeatedLogFilter(logging.Filter)
```

Filter repeated log records.

#### filter

```python
def filter(record: logging.LogRecord) -> bool
```

Determines whether current log is different to last log.

#### call\_potential\_coroutine

```python
async def call_potential_coroutine(
        coroutine_or_return_value: Union[Any, Coroutine]) -> Any
```

Awaits coroutine or returns value directly if it&#x27;s not a coroutine.

**Arguments**:

- `coroutine_or_return_value` - Either the return value of a synchronous function
  call or a coroutine which needs to be await first.
  

**Returns**:

  The return value of the function.

#### directory\_size\_in\_mb

```python
def directory_size_in_mb(
        path: Path,
        filenames_to_exclude: Optional[List[Text]] = None) -> float
```

Calculates the size of a directory.

**Arguments**:

- `path` - The path to the directory.
- `filenames_to_exclude` - Allows excluding certain files from the calculation.
  

**Returns**:

  Directory size in MiB.

#### copy\_directory

```python
def copy_directory(source: Path, destination: Path) -> None
```

Copies the content of one directory into another.

**Arguments**:

- `source` - The directory whose contents should be copied to `destination`.
- `destination` - The directory which should contain the content `source` in the end.
  

**Raises**:

- `ValueError` - If destination is not empty.

#### find\_unavailable\_packages

```python
def find_unavailable_packages(package_names: List[Text]) -> Set[Text]
```

Tries to import all package names and returns the packages where it failed.

**Arguments**:

- `package_names` - The package names to import.
  

**Returns**:

  Package names that could not be imported.

#### module\_path\_from\_class

```python
def module_path_from_class(clazz: Type) -> Text
```

Return the module path of an instance&#x27;s class.

#### get\_bool\_env\_variable

```python
def get_bool_env_variable(variable_name: str,
                          default_variable_value: bool) -> bool
```

Fetch bool value stored in environment variable.

If environment variable is set but value is
not of boolean nature, an exception will be raised.

Args: variable_name:
Name of the environment variable.
default_variable_value: Value to be returned if environment variable is not set.

**Returns**:

  A boolean value stored in the environment variable
  or default value if environment variable is not set.
