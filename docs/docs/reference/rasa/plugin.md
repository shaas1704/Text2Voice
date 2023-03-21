---
sidebar_label: rasa.plugin
title: rasa.plugin
---
#### plugin\_manager

```python
@functools.lru_cache(maxsize=2)
def plugin_manager() -> pluggy.PluginManager
```

Initialises a plugin manager which registers hook implementations.

#### refine\_cli

```python
@hookspec
def refine_cli(subparsers: SubParsersAction,
               parent_parsers: List[argparse.ArgumentParser]) -> None
```

Customizable hook for adding CLI commands.

#### get\_version\_info

```python
@hookspec
def get_version_info() -> Tuple[Text, Text]
```

Hook specification for getting plugin version info.

#### configure\_commandline

```python
@hookspec
def configure_commandline(
        cmdline_arguments: argparse.Namespace) -> Optional[Text]
```

Hook specification for configuring plugin CLI.

#### init\_telemetry

```python
@hookspec
def init_telemetry(endpoints_file: Optional[Text]) -> None
```

Hook specification for initialising plugin telemetry.

#### init\_managers

```python
@hookspec
def init_managers(endpoints_file: Optional[Text]) -> None
```

Hook specification for initialising managers.

#### create\_tracker\_store

```python
@hookspec(firstresult=True)  # type: ignore[misc]
def create_tracker_store(
        endpoint_config: Union["TrackerStore", "EndpointConfig"],
        domain: "Domain",
        event_broker: Optional["EventBroker"] = None) -> "TrackerStore"
```

Hook specification for wrapping with AuthRetryTrackerStore.
