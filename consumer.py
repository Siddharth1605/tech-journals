from kafka import KafkaConsumer
import json
import time
import signal
import sys

consumer = KafkaConsumer(
    "orders",
    bootstrap_servers=["redpanda:9092"],
    group_id="orders-group",
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode("utf-8"))
)

print("Consumer Started")

_shutdown = False

def _handle_sigterm(signum, frame):
    # ADDED: without this, Kubernetes kills the process outright when
    # scaling down, and the consumer never calls close() — so it never
    # sends a LeaveGroup request. The broker then keeps this member
    # around as a zombie until session.timeout.ms expires, which can
    # confuse lag/member-count metrics for the whole group.
    global _shutdown
    print("Received SIGTERM, leaving group cleanly...")
    _shutdown = True

signal.signal(signal.SIGTERM, _handle_sigterm)

for msg in consumer:
    if _shutdown:
        break

    print("Received:", msg.value)

    # simulate heavy processing
    time.sleep(5)

    print("Processed")

consumer.close()  # ADDED: sends LeaveGroup so the coordinator drops this member immediately
print("Consumer shut down cleanly")
sys.exit(0)
