from azure.servicebus import ServiceBusClient, ServiceBusMessage, TransportType
from azure.servicebus._pyamqp import AMQPClient

# Replace with your actual connection string and queue name
connection_string = "Endpoint=sb://172.18.0.3/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=SAS_KEY_VALUE;UseDevelopmentEmulator=true;"
queue_name = "workspacequeue"

from azure.servicebus._pyamqp import AMQPClient
# Disable TLS. Workaround for https://github.com/Azure/azure-sdk-for-python/issues/34273
org_init = AMQPClient.__init__
def new_init(self, hostname, **kwargs):
    kwargs["use_tls"] = False
    org_init(self, hostname, **kwargs)
AMQPClient.__init__ = new_init

# Create a ServiceBusClient using the connection string
servicebus_client = ServiceBusClient.from_connection_string(conn_str=connection_string, logging_enable=True, transport_type=TransportType.Amqp)

# Sending a message to the queue
with servicebus_client:
    sender = servicebus_client.get_queue_sender(queue_name=queue_name)
    with sender:
        message = ServiceBusMessage("Hello, Service Bus!")
        sender.send_messages(message)
        print("Message sent!")

# Receiving a message from the queue
with servicebus_client:
    receiver = servicebus_client.get_queue_receiver(queue_name=queue_name, max_wait_time=5)
    with receiver:
        for msg in receiver:
            print("Received: " + str(msg))
            receiver.complete_message(msg)
