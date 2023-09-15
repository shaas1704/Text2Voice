---
sidebar_label: rasa.engine.graph
title: rasa.engine.graph
---
## SchemaNode Objects

```python
@dataclass
class SchemaNode()
```

Represents one node in the schema.

**Arguments**:

- `needs` - describes which parameters in `fn` (or `constructor_name`
  if `eager==False`) are filled by which parent nodes.
- `uses` - The class which models the behavior of this specific graph node.
- `constructor_name` - The name of the constructor which should be used to
  instantiate the component. If `eager==False` then the `constructor` can
  also specify parameters which are filled by parent nodes. This is e.g.
  useful if a parent node returns a `Resource` and this node wants to
  directly load itself from this resource.
- `fn` - The name of the function which should be called on the instantiated
  component when the graph is executed. The parameters from `needs` are
  filled from the parent nodes.
- `fn`1 - The user&#x27;s configuration for this graph node. This configuration
  does not need to be specify all possible parameters; the default values
  for missing parameters will be filled in later.
- `fn`2 - If `fn`2 then the component is instantiated before the graph is run.
  Otherwise it&#x27;s instantiated as the graph runs (lazily). Usually we always
  instantiated lazily during training and eagerly during inference (to
  avoid that the first prediction takes longer).
- `fn`4 - If `fn`5 then this node can&#x27;t be pruned during fingerprinting
  (it might be replaced with a cached value though). This is e.g. used for
  all components which train as their result always needs to be added to
  the model archive so that the data is available during inference.
- `fn`6 - Nodes with `fn`6 are _always_ run (also during the fingerprint
  run). This makes sure that we e.g. detect changes in file contents.
- `fn`8 - If given, then the graph node is loaded from an existing resource
  instead of instantiated from scratch. This is e.g. used to load a trained
  component for predictions.

## GraphSchema Objects

```python
@dataclass
class GraphSchema()
```

Represents a graph for training a model or making predictions.

#### as\_dict

```python
def as_dict() -> Dict[Text, Any]
```

Returns graph schema in a serializable format.

**Returns**:

  The graph schema in a format which can be dumped as JSON or other formats.

#### from\_dict

```python
@classmethod
def from_dict(cls, serialized_graph_schema: Dict[Text, Any]) -> GraphSchema
```

Loads a graph schema which has been serialized using `schema.as_dict()`.

**Arguments**:

- `serialized_graph_schema` - A serialized graph schema.
  

**Returns**:

  A properly loaded schema.
  

**Raises**:

- `GraphSchemaException` - In case the component class for a node couldn&#x27;t be
  found.

#### target\_names

```python
@property
def target_names() -> List[Text]
```

Returns the names of all target nodes.

#### minimal\_graph\_schema

```python
def minimal_graph_schema(targets: Optional[List[Text]] = None) -> GraphSchema
```

Returns a new schema where all nodes are a descendant of a target.

## GraphComponent Objects

```python
class GraphComponent(ABC)
```

Interface for any component which will run in a graph.

#### required\_components

```python
@classmethod
def required_components(cls) -> List[Type]
```

Components that should be included in the pipeline before this component.

#### create

```python
@classmethod
@abstractmethod
def create(cls, config: Dict[Text, Any], model_storage: ModelStorage,
           resource: Resource,
           execution_context: ExecutionContext) -> GraphComponent
```

Creates a new `GraphComponent`.

**Arguments**:

- `config` - This config overrides the `default_config`.
- `model_storage` - Storage which graph components can use to persist and load
  themselves.
- `resource` - Resource locator for this component which can be used to persist
  and load itself from the `model_storage`.
- `execution_context` - Information about the current graph run.
  
- `Returns` - An instantiated `GraphComponent`.

#### load

```python
@classmethod
def load(cls, config: Dict[Text, Any], model_storage: ModelStorage,
         resource: Resource, execution_context: ExecutionContext,
         **kwargs: Any) -> GraphComponent
```

Creates a component using a persisted version of itself.

If not overridden this method merely calls `create`.

**Arguments**:

- `config` - The config for this graph component. This is the default config of
  the component merged with config specified by the user.
- `model_storage` - Storage which graph components can use to persist and load
  themselves.
- `resource` - Resource locator for this component which can be used to persist
  and load itself from the `model_storage`.
- `execution_context` - Information about the current graph run.
- `kwargs` - Output values from previous nodes might be passed in as `kwargs`.
  

**Returns**:

  An instantiated, loaded `GraphComponent`.

#### get\_default\_config

```python
@staticmethod
def get_default_config() -> Dict[Text, Any]
```

Returns the component&#x27;s default config.

Default config and user config are merged by the `GraphNode` before the
config is passed to the `create` and `load` method of the component.

**Returns**:

  The default config of the component.

#### supported\_languages

```python
@staticmethod
def supported_languages() -> Optional[List[Text]]
```

Determines which languages this component can work with.

Returns: A list of supported languages, or `None` to signify all are supported.

#### not\_supported\_languages

```python
@staticmethod
def not_supported_languages() -> Optional[List[Text]]
```

Determines which languages this component cannot work with.

Returns: A list of not supported languages, or
`None` to signify all are supported.

#### required\_packages

```python
@staticmethod
def required_packages() -> List[Text]
```

Any extra python dependencies required for this component to run.

#### fingerprint\_addon

```python
@classmethod
def fingerprint_addon(cls, config: Dict[str, Any]) -> Optional[str]
```

Adds additional data to the fingerprint calculation.

This is useful if a component uses external data that is not provided
by the graph.

## GraphNodeHook Objects

```python
class GraphNodeHook(ABC)
```

Holds functionality to be run before and after a `GraphNode`.

#### on\_before\_node

```python
@abstractmethod
def on_before_node(node_name: Text, execution_context: ExecutionContext,
                   config: Dict[Text, Any],
                   received_inputs: Dict[Text, Any]) -> Dict
```

Runs before the `GraphNode` executes.

**Arguments**:

- `node_name` - The name of the node being run.
- `execution_context` - The execution context of the current graph run.
- `config` - The node&#x27;s config.
- `received_inputs` - Mapping from parameter name to input value.
  

**Returns**:

  Data that is then passed to `on_after_node`

#### on\_after\_node

```python
@abstractmethod
def on_after_node(node_name: Text, execution_context: ExecutionContext,
                  config: Dict[Text, Any], output: Any,
                  input_hook_data: Dict) -> None
```

Runs after the `GraphNode` as executed.

**Arguments**:

- `node_name` - The name of the node that has run.
- `execution_context` - The execution context of the current graph run.
- `config` - The node&#x27;s config.
- `output` - The output of the node.
- `input_hook_data` - Data returned from `on_before_node`.

## ExecutionContext Objects

```python
@dataclass
class ExecutionContext()
```

Holds information about a single graph run.

## GraphNode Objects

```python
class GraphNode()
```

Instantiates and runs a `GraphComponent` within a graph.

A `GraphNode` is a wrapper for a `GraphComponent` that allows it to be executed
in the context of a graph. It is responsible for instantiating the component at the
correct time, collecting the inputs from the parent nodes, running the run function
of the component and passing the output onwards.

#### \_\_init\_\_

```python
def __init__(node_name: Text,
             component_class: Type[GraphComponent],
             constructor_name: Text,
             component_config: Dict[Text, Any],
             fn_name: Text,
             inputs: Dict[Text, Text],
             eager: bool,
             model_storage: ModelStorage,
             resource: Optional[Resource],
             execution_context: ExecutionContext,
             hooks: Optional[List[GraphNodeHook]] = None) -> None
```

Initializes `GraphNode`.

**Arguments**:

- `node_name` - The name of the node in the schema.
- `component_class` - The class to be instantiated and run.
- `constructor_name` - The method used to instantiate the component.
- `component_config` - Config to be passed to the component.
- `fn_name` - The function on the instantiated `GraphComponent` to be run when
  the node executes.
- `inputs` - A map from input name to parent node name that provides it.
- `eager` - Determines if the node is instantiated right away, or just before
  being run.
- `model_storage` - Storage which graph components can use to persist and load
  themselves.
- `node_name`0 - If given the `GraphComponent` will be loaded from the
  `model_storage` using the given resource.
- `node_name`3 - Information about the current graph run.
- `node_name`4 - These are called before and after execution.

#### \_\_call\_\_

```python
def __call__(
    *inputs_from_previous_nodes: Union[Tuple[Text, Any], Text]
) -> Tuple[Text, Any]
```

Calls the `GraphComponent` run method when the node executes in the graph.

**Arguments**:

- `*inputs_from_previous_nodes` - The output of all parent nodes. Each is a
  dictionary with a single item mapping the node&#x27;s name to its output.
  If the node couldn&#x27;t be resolved and has no output, the node name is
  provided instead of a tuple.
  

**Returns**:

  The node name and its output.

#### from\_schema\_node

```python
@classmethod
def from_schema_node(cls,
                     node_name: Text,
                     schema_node: SchemaNode,
                     model_storage: ModelStorage,
                     execution_context: ExecutionContext,
                     hooks: Optional[List[GraphNodeHook]] = None) -> GraphNode
```

Creates a `GraphNode` from a `SchemaNode`.

## GraphModelConfiguration Objects

```python
@dataclass()
class GraphModelConfiguration()
```

The model configuration to run as a graph during training and prediction.
