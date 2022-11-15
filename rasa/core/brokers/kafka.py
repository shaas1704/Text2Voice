import os
import json
import logging
from asyncio import AbstractEventLoop
from typing import Any, Text, List, Optional, Union, Dict, TYPE_CHECKING
import time

from rasa.core.brokers.broker import EventBroker
from rasa.shared.utils.io import DEFAULT_ENCODING
from rasa.utils.endpoints import EndpointConfig
from rasa.shared.exceptions import RasaException
import rasa.shared.utils.common

if TYPE_CHECKING:
    from confluent_kafka import KafkaError, SerializingProducer

logger = logging.getLogger(__name__)


class KafkaProducerInitializationError(RasaException):
    """Raised if the Kafka Producer cannot be properly initialized."""


class KafkaEventBroker(EventBroker):
    """Kafka event broker."""

    def __init__(
        self,
        url: Union[Text, List[Text], None],
        topic: Text = "rasa_core_events",
        client_id: Optional[Text] = None,
        partition_by_sender: bool = False,
        sasl_username: Optional[Text] = None,
        sasl_password: Optional[Text] = None,
        sasl_mechanism: Optional[Text] = "PLAIN",
        ssl_cafile: Optional[Text] = None,
        ssl_certfile: Optional[Text] = None,
        ssl_keyfile: Optional[Text] = None,
        ssl_check_hostname: bool = False,
        security_protocol: Text = "SASL_PLAINTEXT",
        **kwargs: Any,
    ) -> None:
        """Kafka event broker.

        Args:
            url: 'url[:port]' string (or list of 'url[:port]'
                strings) that the producer should contact to bootstrap initial
                cluster metadata. This does not have to be the full node list.
                It just needs to have at least one broker that will respond to a
                Metadata API Request.
            topic: Topics to subscribe to.
            client_id: A name for this client. This string is passed in each request
                to servers and can be used to identify specific server-side log entries
                that correspond to this client. Also submitted to `GroupCoordinator` for
                logging with respect to producer group administration.
            partition_by_sender: Flag to configure whether messages are partitioned by
                sender_id or not
            sasl_username: Username for plain authentication.
            sasl_password: Password for plain authentication.
            sasl_mechanism: Authentication mechanism when security_protocol is
                configured for SASL_PLAINTEXT or SASL_SSL.
                Valid values are: PLAIN, GSSAPI, OAUTHBEARER, SCRAM-SHA-256,
                SCRAM-SHA-512. Default: `PLAIN`
            ssl_cafile: Optional filename of ca file to use in certificate
                verification.
            ssl_certfile: Optional filename of file in pem format containing
                the client certificate, as well as any ca certificates needed to
                establish the certificate's authenticity.
            ssl_keyfile: Optional filename containing the client private key.
            ssl_check_hostname: Flag to configure whether ssl handshake
                should verify that the certificate matches the broker's hostname.
            security_protocol: Protocol used to communicate with brokers.
                Valid values are: PLAINTEXT, SSL, SASL_PLAINTEXT, SASL_SSL.
        """
        self.producer: Optional[SerializingProducer] = None
        self.url = url
        self.topic = topic
        self.client_id = client_id
        self.partition_by_sender = partition_by_sender
        self.security_protocol = security_protocol.upper()
        self.sasl_username = sasl_username
        self.sasl_password = sasl_password
        self.sasl_mechanism = sasl_mechanism
        self.ssl_cafile = ssl_cafile
        self.ssl_certfile = ssl_certfile
        self.ssl_keyfile = ssl_keyfile
        self.ssl_check_hostname = "https" if ssl_check_hostname else None

    @classmethod
    async def from_endpoint_config(
        cls,
        broker_config: EndpointConfig,
        event_loop: Optional[AbstractEventLoop] = None,
    ) -> Optional["KafkaEventBroker"]:
        """Creates broker. See the parent class for more information."""
        if broker_config is None:
            return None

        return cls(broker_config.url, **broker_config.kwargs)

    def publish(
        self,
        event: Dict[Text, Any],
        retries: int = 60,
        retry_delay_in_seconds: float = 5,
    ) -> None:
        """Publishes events."""
        from confluent_kafka import KafkaException

        if self.producer is None:
            self.producer = self._create_producer()
            try:
                self.producer.flush(timeout=1)
                logger.debug("Connection to kafka successful.")
            except KafkaException:
                logger.debug("Failed to connect kafka.")
                return
        while retries:
            try:
                self._publish(event)
                return
            except Exception as e:
                logger.error(
                    f"Could not publish message to kafka url '{self.url}'. "
                    f"Failed with error: {e}"
                )
                try:
                    self.producer.flush(timeout=1)
                except KafkaException:
                    logger.debug("Connection to kafka lost, reconnecting...")
                    self.producer = self._create_producer()
                    try:
                        self.producer.flush(timeout=1)
                        logger.debug("Reconnection to kafka successful")
                        self._publish(event)
                    except KafkaException:
                        pass
                retries -= 1
                time.sleep(retry_delay_in_seconds)

        logger.error("Failed to publish Kafka event.")

    def _create_producer(self) -> "SerializingProducer":
        import confluent_kafka

        if self.security_protocol == "PLAINTEXT":
            authentication_params: Dict[Text, Any] = {
                "security.protocol": self.security_protocol.lower(),
            }
        elif self.security_protocol == "SASL_PLAINTEXT":
            authentication_params = {
                "sasl.username": self.sasl_username,
                "sasl.password": self.sasl_password,
                "sasl.mechanism": self.sasl_mechanism,
                "security.protocol": self.security_protocol.lower(),
            }
        elif self.security_protocol == "SSL":
            authentication_params = {
                "ssl.ca.location": self.ssl_cafile,
                "ssl.certificate.location": self.ssl_certfile,
                "ssl.key.location": self.ssl_keyfile,
                "security.protocol": self.security_protocol.lower(),
            }
        elif self.security_protocol == "SASL_SSL":
            authentication_params = {
                "sasl.username": self.sasl_username,
                "sasl.password": self.sasl_password,
                "ssl.ca.location": self.ssl_cafile,
                "ssl.certificate.location": self.ssl_certfile,
                "ssl.key.location": self.ssl_keyfile,
                "ssl.endpoint.identification.algorithm": self.ssl_check_hostname,
                "security.protocol": self.security_protocol.lower(),
                "sasl.mechanism": self.sasl_mechanism,
            }
        else:
            raise ValueError(
                f"Cannot initialise `KafkaEventBroker`: "
                f"Invalid `security_protocol` ('{self.security_protocol}')."
            )

        try:
            return confluent_kafka.SerializingProducer(
                {
                    "client.id": self.client_id,
                    "bootstrap.servers": self.url,
                    "value.serializer": lambda v, ctx: json.dumps(v).encode(
                        DEFAULT_ENCODING
                    ),
                    "error_cb": kafka_error_callback,
                    **authentication_params,
                }
            )
        except confluent_kafka.KafkaException as e:
            raise KafkaProducerInitializationError(
                f"Cannot initialise `KafkaEventBroker`: {e}"
            )

    def _publish(self, event: Dict[Text, Any]) -> None:
        if self.partition_by_sender:
            partition_key = bytes(event.get("sender_id"), encoding=DEFAULT_ENCODING)
        else:
            partition_key = None

        headers = []
        if self.rasa_environment:
            headers = [
                (
                    "RASA_ENVIRONMENT",
                    bytes(self.rasa_environment, encoding=DEFAULT_ENCODING),
                )
            ]

        logger.debug(
            f"Calling kafka send({self.topic}, value={event},"
            f" key={partition_key!s}, headers={headers})"
        )

        if self.producer is not None:
            self.producer.produce(
                self.topic, value=event, key=partition_key, headers=headers
            )

    @rasa.shared.utils.common.lazy_property
    def rasa_environment(self) -> Optional[Text]:
        """Get value of the `RASA_ENVIRONMENT` environment variable."""
        return os.environ.get("RASA_ENVIRONMENT", "RASA_ENVIRONMENT_NOT_SET")


def kafka_error_callback(err: "KafkaError") -> None:
    """Callback for Kafka errors.

    Any exception raised from this callback will be re-raised from the
    triggering flush() call.
    """
    from confluent_kafka import KafkaException

    raise KafkaException(err)
