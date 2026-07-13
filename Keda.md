Yes, avi. That command only waits for Kafka to become ready. It does not build or deploy the producer and consumer. Right now, don’t continue until Kafka becomes 1/1 Running.

Your full flow should be:

KEDA installed
      ↓
Deploy Kafka
      ↓
Wait for Kafka to become Ready
      ↓
Create Kafka topic
      ↓
Build producer and consumer JARs
      ↓
Build Docker images inside Minikube
      ↓
Deploy producer
      ↓
Deploy consumer
      ↓
Deploy KEDA ScaledObject
      ↓
Send messages through producer
      ↓
Watch KEDA scale consumer pods

For your current command:

kubectl rollout status deployment/kafka \
  --timeout=180s

If it is still waiting, open another terminal and run:

kubectl get pods

You may see:

kafka-xxxxxxxxxx   0/1   Running

or:

kafka-xxxxxxxxxx   0/1   ContainerCreating

Wait a little. Kafka can take 30–90 seconds to initialize.

If it becomes:

kafka-xxxxxxxxxx   1/1   Running

your first terminal will print:

deployment "kafka" successfully rolled out

Then continue with the following exact sequence.

Step 1: Check Kafka

kubectl get pods

Expected:

NAME                     READY   STATUS
kafka-xxxxxxxxxx         1/1     Running

If it remains 0/1 after three minutes, run:

kubectl describe pod \
  -l app=kafka

Then:

kubectl logs deployment/kafka \
  --tail=100

Do not deploy the applications until Kafka is ready.


---

Step 2: Create the Kafka topic

After Kafka becomes 1/1 Running:

kubectl exec deployment/kafka -- \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create \
  --if-not-exists \
  --topic orders \
  --partitions 6 \
  --replication-factor 1

Expected:

Created topic orders.

Verify:

kubectl exec deployment/kafka -- \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --topic orders

Expected:

Topic: orders
PartitionCount: 6
ReplicationFactor: 1


---

Step 3: Build the producer Spring Boot application

You should currently be here:

~/k8s-keda/tech-journals/kafka-keda-demo

Check:

ls

Expected:

README.md
consumer
k8s
producer

Build producer:

mvn -f producer/pom.xml \
  clean package \
  -DskipTests

After it succeeds:

BUILD SUCCESS

Verify the JAR:

ls producer/target/

You should see:

kafka-producer-1.0.0.jar


---

Step 4: Build the consumer Spring Boot application

mvn -f consumer/pom.xml \
  clean package \
  -DskipTests

Expected:

BUILD SUCCESS

Verify:

ls consumer/target/

You should see:

kafka-consumer-1.0.0.jar


---

Step 5: Point Docker to Minikube

This step is important because you faced the local-image problem earlier.

Run:

eval $(minikube docker-env)

This changes the current terminal so that Docker builds directly into Minikube’s Docker environment.

Verify:

echo $DOCKER_HOST

You should see something similar to:

tcp://192.168.49.2:2376

Now build both images.

Producer:

docker build \
  -t kafka-producer:1.0 \
  ./producer

Consumer:

docker build \
  -t kafka-consumer:1.0 \
  ./consumer

Verify:

docker images | grep kafka

Expected:

kafka-consumer   1.0
kafka-producer   1.0

You may also see the Apache Kafka image.


---

Step 6: Deploy the producer

kubectl apply \
  -f k8s/producer.yaml

Expected:

deployment.apps/kafka-producer created
service/kafka-producer created

Wait:

kubectl rollout status \
  deployment/kafka-producer \
  --timeout=180s

Expected:

deployment "kafka-producer" successfully rolled out

Check:

kubectl get pods

Expected:

kafka-xxxxxxxxxx            1/1   Running
kafka-producer-xxxxxxxxxx   1/1   Running


---

Step 7: Deploy the consumer

Run:

kubectl apply \
  -f k8s/consumer.yaml

Expected:

deployment.apps/kafka-consumer created

Check:

kubectl get deployment

You may see:

NAME             READY   UP-TO-DATE   AVAILABLE

kafka            1/1     1            1

kafka-producer   1/1     1            1

kafka-consumer   0/0     0            0

kafka-consumer 0/0 is correct.

The YAML contains:

replicas: 0

KEDA will create consumer pods only when Kafka has pending messages.


---

Step 8: Deploy the KEDA ScaledObject

kubectl apply \
  -f k8s/keda-scaled-object.yaml

Expected:

scaledobject.keda.sh/kafka-consumer-scaler created

Check:

kubectl get scaledobject

Initially, you may see:

NAME                    SCALETARGETKIND      READY   ACTIVE

kafka-consumer-scaler   apps/v1.Deployment  True    False

Meaning:

READY = True
KEDA configuration works

ACTIVE = False
No Kafka consumer lag currently exists

Check the HPA:

kubectl get hpa

Expected:

keda-hpa-kafka-consumer-scaler


---

Step 9: Expose the producer locally

Because the producer Service is ClusterIP, use port forwarding:

kubectl port-forward \
  service/kafka-producer \
  8080:8080

Expected:

Forwarding from 127.0.0.1:8080 -> 8080

Keep this terminal open.

Do not press Ctrl+C.


---

Step 10: Watch consumer scaling

Open another terminal.

Run:

kubectl get pods -w

Initially:

kafka-xxxxxxxxxx            1/1   Running

kafka-producer-xxxxxxxxxx   1/1   Running

There should be no consumer pod yet.


---

Step 11: Publish 100 Kafka messages

Open one more terminal:

curl -X POST \
  http://localhost:8080/orders/publish/100

Expected:

100 orders published to topic orders

Now check the terminal running:

kubectl get pods -w

You should see consumer pods appearing:

kafka-consumer-xxxxxxxxxx   0/1   Pending

kafka-consumer-xxxxxxxxxx   0/1   ContainerCreating

kafka-consumer-xxxxxxxxxx   1/1   Running

Then KEDA may scale further:

kafka-consumer-aaa   1/1   Running

kafka-consumer-bbb   1/1   Running

kafka-consumer-ccc   1/1   Running

kafka-consumer-ddd   1/1   Running

Depending on the lag, it can scale up to six consumer pods.


---

Step 12: Watch KEDA and HPA

Run:

watch -n 2 \
'kubectl get deployment kafka-consumer; echo; kubectl get hpa; echo; kubectl get scaledobject'

You may see:

NAME             READY   UP-TO-DATE

kafka-consumer   6/6     6

After consumers finish processing all messages, KEDA waits for the cooldown period and scales down:

6 → 5 → 4 → 3 → 2 → 1 → 0


---

Step 13: View consumer logs

kubectl logs \
  -l app=kafka-consumer \
  --prefix=true \
  --tail=200

You should see:

[pod-name] START partition=2 offset=10

[pod-name] DONE partition=2 offset=10


---

For now, you are only at this stage:

KEDA             ✅

Kafka Deployment ⏳ currently starting

Kafka topic      ❌ not yet

Producer build   ❌ not yet

Consumer build   ❌ not yet

Docker images    ❌ not yet

Applications     ❌ not yet

ScaledObject     ❌ not yet

First, run this in another terminal:

kubectl get pods

If Kafka is still 0/1, send me that output plus:

kubectl logs deployment/kafka \
  --tail=50

Then we can check why its readiness is waiting before moving to the producer and consumer.
