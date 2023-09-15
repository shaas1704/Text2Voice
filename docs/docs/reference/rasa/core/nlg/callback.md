---
sidebar_label: rasa.core.nlg.callback
title: rasa.core.nlg.callback
---
#### nlg\_response\_format\_spec

```python
def nlg_response_format_spec() -> Dict[Text, Any]
```

Expected response schema for an NLG endpoint.

Used for validation of the response returned from the NLG endpoint.

#### nlg\_request\_format

```python
def nlg_request_format(utter_action: Text, tracker: DialogueStateTracker,
                       output_channel: Text, **kwargs: Any) -> Dict[Text, Any]
```

Create the json body for the NLG json body for the request.

## CallbackNaturalLanguageGenerator Objects

```python
class CallbackNaturalLanguageGenerator(NaturalLanguageGenerator)
```

Generate bot utterances by using a remote endpoint for the generation.

The generator will call the endpoint for each message it wants to
generate. The endpoint needs to respond with a properly formatted
json. The generator will use this message to create a response for
the bot.

#### generate

```python
async def generate(utter_action: Text, tracker: DialogueStateTracker,
                   output_channel: Text, **kwargs: Any) -> Dict[Text, Any]
```

Retrieve a named response from the domain using an endpoint.

#### validate\_response

```python
@staticmethod
def validate_response(content: Optional[Dict[Text, Any]]) -> bool
```

Validate the NLG response. Raises exception on failure.

#### fetch\_response\_id

```python
@staticmethod
def fetch_response_id(
    utter_action: Text, tracker: DialogueStateTracker, output_channel: Text,
    domain_responses: Optional[Dict[Text, List[Dict[Text, Any]]]]
) -> Optional[Text]
```

Fetch the response id for the utter action.

The response id is retrieved from the domain responses for the
utter action given the tracker state and channel.
