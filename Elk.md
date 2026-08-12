
And I want to make one correction to my earlier recommendation: for Kubernetes, the clean architecture is Filebeat → Logstash → Elasticsearch → Kibana, not Logstash directly tailing every node's files. Elastic's Kubernetes guidance uses Filebeat as a DaemonSet because it runs on each node and reads /var/log/containers; Logstash then receives Beats events on port 5044. 

Your Elasticsearch is already 9.4.3, so we'll keep everything on 9.4.3 rather than mixing versions. Elastic publishes both Filebeat and Logstash 9.4.3 images. 


---

Target architecture

Kubernetes
┌───────────────────────────────────────────────┐
│                                               │
│  Application Pods                             │
│       │                                       │
│       │ container logs                        │
│       ▼                                       │
│  /var/log/containers/*.log                    │
│       │                                       │
│       ▼                                       │
│  Filebeat DaemonSet                           │
│  (one per node)                               │
│       │                                       │
│       │ Beats protocol :5044                  │
│       ▼                                       │
│  Logstash                                    │
│  Deployment, 1 replica                        │
│       │                                       │
│       │ HTTPS :9200                           │
│       ▼                                       │
│  Elasticsearch 9.4.3                         │
│       │                                       │
│       ▼                                       │
│  Kibana                                      │
│                                               │
└───────────────────────────────────────────────┘

This gives you a proper ELK pipeline:

Filebeat = collection
Logstash = processing/routing
Elasticsearch = storage/search
Kibana = visualization

Elastic also provides an ECK-native Logstash resource if you already have ECK installed; ECK supports Logstash 8.7+ and the current quickstart uses a Beats input on 5044. 


---

Important: don't reinstall Elasticsearch/Kibana

You currently have:

logging-es-default-0       1/1 Running
logging-kb-...             1/1 Running

and:

Elasticsearch 9.4.3
PHASE Ready

Keep them.

Your yellow status with one node isn't a reason to reinstall. The primary objective here is simply to replace:

Fluent Bit → Elasticsearch

with:

Filebeat → Logstash → Elasticsearch


---

Step 0 — remove Fluent Bit

Once we're ready to switch, remove your current Fluent Bit resources.

First inspect what owns them:

kubectl get all -n logging

Then remove the Fluent Bit DaemonSet and ConfigMap.

If they are named exactly as you've shown:

kubectl delete daemonset fluent-bit -n logging
kubectl delete configmap fluent-bit -n logging
kubectl delete service fluent-bit -n logging

If your ConfigMap/DaemonSet was installed by Helm, don't use the above; tell me the Helm release first.

Check:

helm list -n logging


---

Step 1 — create a clean ELK namespace

I'd keep the ingestion components in the same logging namespace as your ES/Kibana.

kubectl create namespace logging --dry-run=client -o yaml | kubectl apply -f -


---

Step 2 — create the Elasticsearch credentials Secret

You already have the elastic password, but don't put it directly into Logstash configuration.

Create:

kubectl create secret generic elastic-credentials \
  -n logging \
  --from-literal=username=elastic \
  --from-literal=password='<YOUR_ELASTIC_PASSWORD>'

Check:

kubectl get secret elastic-credentials -n logging

Do not print the secret with -o yaml and paste it here.

Elastic security requires credentials when security is enabled, which it is in modern Elasticsearch installations. 


---

Step 3 — deploy Logstash

I'm deliberately using a normal Kubernetes Deployment here rather than introducing another ECK CRD dependency.

Create:

cat > logstash.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: logstash-pipeline
  namespace: logging
data:
  logstash.conf: |
    input {
      beats {
        port => 5044
      }
    }

    filter {
      mutate {
        add_field => {
          "[event][dataset]" => "kubernetes"
        }
      }
    }

    output {
      elasticsearch {
        hosts => ["https://logging-es-http.logging.svc:9200"]

        user => "${ELASTICSEARCH_USERNAME}"
        password => "${ELASTICSEARCH_PASSWORD}"

        ssl_enabled => true
        ssl_verification_mode => "none"

        index => "kubernetes-logs-%{+YYYY.MM.dd}"
      }

      stdout {
        codec => rubydebug
      }
    }

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: logstash-settings
  namespace: logging
data:
  logstash.yml: |
    http.host: 0.0.0.0
    xpack.monitoring.enabled: false

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: logstash
  namespace: logging
spec:
  replicas: 1

  selector:
    matchLabels:
      app: logstash

  template:
    metadata:
      labels:
        app: logstash

    spec:
      containers:
        - name: logstash
          image: docker.elastic.co/logstash/logstash:9.4.3

          ports:
            - name: beats
              containerPort: 5044

            - name: http
              containerPort: 9600

          env:
            - name: ELASTICSEARCH_USERNAME
              valueFrom:
                secretKeyRef:
                  name: elastic-credentials
                  key: username

            - name: ELASTICSEARCH_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: elastic-credentials
                  key: password

          resources:
            requests:
              cpu: 250m
              memory: 512Mi

            limits:
              cpu: "1"
              memory: 1Gi

          volumeMounts:
            - name: pipeline
              mountPath: /usr/share/logstash/pipeline/logstash.conf
              subPath: logstash.conf

            - name: settings
              mountPath: /usr/share/logstash/config/logstash.yml
              subPath: logstash.yml

      volumes:
        - name: pipeline
          configMap:
            name: logstash-pipeline

        - name: settings
          configMap:
            name: logstash-settings

---
apiVersion: v1
kind: Service
metadata:
  name: logstash
  namespace: logging
spec:
  selector:
    app: logstash

  ports:
    - name: beats
      port: 5044
      targetPort: 5044

    - name: http
      port: 9600
      targetPort: 9600
EOF

kubectl apply -f logstash.yaml

The Logstash Beats input on 5044 is the standard Filebeat → Logstash pattern. 


---

Step 4 — verify Logstash BEFORE installing Filebeat

This is important.

Don't install the entire pipeline and then wonder which component failed.

First:

kubectl get pods -n logging

You want:

logstash-xxxxxxxxxx-xxxxx   1/1   Running

Then:

kubectl logs -n logging deployment/logstash

You should eventually see something indicating the Beats input is listening.

Also:

kubectl get svc logstash -n logging

Expected:

logstash   ClusterIP   ...   5044/TCP,9600/TCP


---

Step 5 — verify Logstash → Elasticsearch

Before introducing Filebeat, test the Logstash pod's connectivity to Elasticsearch.

Get the pod:

kubectl get pod -n logging -l app=logstash

Then:

kubectl exec -n logging deploy/logstash -- \
  curl -k -u 'elastic:<YOUR_PASSWORD>' \
  https://logging-es-http.logging.svc:9200/

If curl isn't present in the image, that's okay — don't modify the container.

Use a temporary curl pod:

kubectl run es-test \
  -n logging \
  --rm -it \
  --restart=Never \
  --image=curlimages/curl \
  -- \
  curl -k -u 'elastic:<YOUR_PASSWORD>' \
  https://logging-es-http.logging.svc:9200/

You should get Elasticsearch JSON showing:

version: 9.4.3
cluster_name: logging

If this test fails, stop here. Don't deploy Filebeat yet.


---

Step 6 — deploy Filebeat as a DaemonSet

This is the part that replaces your Fluent Bit.

Elastic's current Kubernetes documentation recommends a Filebeat DaemonSet with /var/log/containers mounted from the host. 

Create:

cat > filebeat.yaml <<'EOF'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: filebeat
  namespace: logging

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: filebeat
rules:
  - apiGroups: [""]
    resources:
      - pods
      - namespaces
      - nodes
    verbs:
      - get
      - list
      - watch

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: filebeat
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: filebeat
subjects:
  - kind: ServiceAccount
    name: filebeat
    namespace: logging

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: filebeat-config
  namespace: logging
data:
  filebeat.yml: |
    filebeat.autodiscover:
      providers:
        - type: kubernetes
          node: ${NODE_NAME}

          templates:
            - config:
                - type: filestream

                  id: "kubernetes-${data.kubernetes.container.id}"

                  paths:
                    - /var/log/containers/*-${data.kubernetes.container.id}.log

                  parsers:
                    - container:
                        stream: all
                        format: auto

                  prospector.scanner.symlinks: true

                  fields:
                    log_source: kubernetes

                  fields_under_root: true

                  close_inactive: 5m

                  clean_inactive: 24h

                  ignore_older: 24h

          hints:
            enabled: false

    processors:
      - add_kubernetes_metadata:
          host: ${NODE_NAME}
          matchers:
            - logs_path:
                logs_path: "/var/log/containers/"

    output.logstash:
      hosts:
        - "logstash.logging.svc:5044"

    logging.level: info

---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: filebeat
  namespace: logging
spec:
  selector:
    matchLabels:
      app: filebeat

  template:
    metadata:
      labels:
        app: filebeat

    spec:
      serviceAccountName: filebeat

      tolerations:
        - operator: Exists

      containers:
        - name: filebeat

          image: docker.elastic.co/beats/filebeat:9.4.3

          args:
            - "-e"
            - "-c"
            - "/etc/filebeat.yml"

          env:
            - name: NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName

          securityContext:
            runAsUser: 0

          resources:
            requests:
              cpu: 50m
              memory: 100Mi

            limits:
              cpu: 500m
              memory: 300Mi

          volumeMounts:
            - name: config
              mountPath: /etc/filebeat.yml
              subPath: filebeat.yml
              readOnly: true

            - name: varlogcontainers
              mountPath: /var/log/containers
              readOnly: true

            - name: varlogpods
              mountPath: /var/log/pods
              readOnly: true

            - name: data
              mountPath: /usr/share/filebeat/data

      volumes:
        - name: config
          configMap:
            name: filebeat-config

        - name: varlogcontainers
          hostPath:
            path: /var/log/containers
            type: Directory

        - name: varlogpods
          hostPath:
            path: /var/log/pods
            type: Directory

        - name: data
          hostPath:
            path: /var/lib/filebeat-data
            type: DirectoryOrCreate
EOF

kubectl apply -f filebeat.yaml


---

Step 7 — verify Filebeat

kubectl get pods -n logging -l app=filebeat -o wide

For your one-node lab you should see:

filebeat-xxxxx   1/1   Running

Then:

kubectl logs -n logging -l app=filebeat --tail=100

You're looking for something along the lines of:

Connection to logstash.logging.svc:5044 established

and harvesting activity.


---

Step 8 — verify Logstash receives Filebeat events

Now:

kubectl logs -n logging deployment/logstash --tail=100

Because we deliberately added:

stdout {
  codec => rubydebug
}

you should see actual events arriving.

For example:

{
    "@timestamp" => ...,
    "message" => "...",
    "kubernetes" => {
       ...
    }
}

This is extremely useful for your lab.

It gives us a clean diagnostic boundary:

Filebeat
   ↓
Logstash
   ↓
stdout

If you see events here:

Filebeat → Logstash is working.


---

Step 9 — verify Elasticsearch indices

Now:

kubectl run es-test \
  -n logging \
  --rm -it \
  --restart=Never \
  --image=curlimages/curl \
  -- \
  curl -k -u 'elastic:<YOUR_PASSWORD>' \
  'https://logging-es-http.logging.svc:9200/_cat/indices?v'

You should eventually see:

kubernetes-logs-2026.08.11

or whatever today's date is in Elasticsearch's timezone.

Then:

curl ...

against:

https://logging-es-http.logging.svc:9200/kubernetes-logs-*/_search

and confirm documents exist.


---

Step 10 — Kibana

Your Kibana service is already:

logging-kb-http
NodePort
5601:30753

So you don't need to reinstall Kibana.

Access it using your existing NodePort:

<k8s-node-ip>:30753

Login:

elastic

with your password.

Then go to:

Stack Management → Data Views

Create:

kubernetes-logs-*

Timestamp field:

@timestamp

Then open Discover.

You should see:

message
kubernetes.namespace
kubernetes.pod.name
kubernetes.container.name
kubernetes.node.name
@timestamp


---

What about your huge XML logs?

Here's the nice part.

Don't start by changing anything for the XML.

First get:

Application
   ↓
Filebeat
   ↓
Logstash
   ↓
Elasticsearch
   ↓
Kibana

working with ordinary Kubernetes logs.

Then test the application producing the huge XML.

If it fails, we now have a much cleaner diagnostic chain.

For example:

Filebeat → Logstash
             ↓
          receives XML
             ↓
          Elasticsearch
             X

Then the problem is almost certainly at the Logstash → ES stage.

If Filebeat itself reports a problem reading the XML, then the log format/size is the culprit.


---

One change I'd make specifically for your lab

Because you're using a single-node Elasticsearch, I'd change the replica count to zero for your log indices.

Otherwise you'll keep seeing yellow health because Elasticsearch can't allocate replicas on another node.

After the first index appears:

kubectl run es-test \
  -n logging \
  --rm -it \
  --restart=Never \
  --image=curlimages/curl \
  -- \
  curl -k -u 'elastic:<YOUR_PASSWORD>' \
  -X PUT \
  'https://logging-es-http.logging.svc:9200/kubernetes-logs-*/_settings' \
  -H 'Content-Type: application/json' \
  -d '{"index":{"number_of_replicas":0}}'

For a lab, this is reasonable.

Do not do this in a production cluster just because it's convenient.


---

Why I'm choosing this setup

There are a few deliberate decisions here.

Filebeat is a DaemonSet

You need one log collector on each Kubernetes node. That's exactly the Kubernetes pattern Elastic documents. 

Filebeat does NOT connect directly to ES

It connects to:

logstash.logging.svc:5044

which gives you:

collection ≠ processing ≠ storage

and makes Logstash useful rather than decorative.

Logstash is only one replica

Your lab has one node and presumably limited CPU/RAM.

Don't start with:

3 Logstash
3 ES
3 Kibana

That's overkill.

Start:

1 Filebeat per node
1 Logstash
1 Elasticsearch
1 Kibana

Elasticsearch remains your existing 9.4.3

No unnecessary reinstall.

Filebeat and Logstash are also 9.4.3

Elastic currently publishes 9.4.3 images for both. 


---

One important security improvement

I deliberately used:

Kubernetes Secret
       ↓
Logstash environment
       ↓
Elasticsearch

rather than putting the password directly in:

logstash.conf

Your earlier Fluent Bit ConfigMap exposed the elastic password. Rotate that password after this setup if that credential has been shared anywhere outside your private environment.

For this lab I also used:

ssl_verification_mode => "none"

because your ECK Elasticsearch uses HTTPS and we want to eliminate certificate-trust complexity while getting the pipeline working.

Once the pipeline works, we can switch this to proper CA verification. ECK's own Logstash quickstart uses the Elasticsearch CA supplied to Logstash rather than disabling verification. 


---

Final topology you should end up with

KUBERNETES
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   Application Pod                                       │
│        │                                                │
│        ▼                                                │
│   /var/log/containers/*.log                             │
│        │                                                │
│        ▼                                                │
│   ┌─────────────────┐                                   │
│   │    Filebeat     │ ← DaemonSet                      │
│   │    9.4.3        │                                   │
│   └────────┬────────┘                                   │
│            │                                            │
│            │ Beats :5044                                │
│            ▼                                            │
│   ┌─────────────────┐                                   │
│   │    Logstash     │ ← Deployment                      │
│   │    9.4.3        │                                   │
│   └────────┬────────┘                                   │
│            │                                            │
│            │ HTTPS :9200                                │
│            ▼                                            │
│   ┌─────────────────┐                                   │
│   │ Elasticsearch    │ ← ECK                            │
│   │    9.4.3         │                                   │
│   └────────┬────────┘                                   │
│            │                                            │
│            ▼                                            │
│   ┌─────────────────┐                                   │
│   │     Kibana      │ ← ECK                            │
│   │    9.4.3         │                                   │
│   └─────────────────┘                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘

Do it in this order

1. Keep existing ES/Kibana
2. Remove Fluent Bit
3. Create elastic-credentials Secret
4. Deploy Logstash
5. Verify Logstash is Running
6. Test Logstash → ES
7. Deploy Filebeat
8. Verify Filebeat → Logstash
9. Verify Logstash → ES indices
10. Open Kibana
11. Create kubernetes-logs-* Data View
12. Only then test the huge XML application

Don't apply everything at once. The staged verification is the part that will save you from another "everything is green but no logs appear" situation. Elastic's own Logstash-on-ECK examples follow the same basic Beats → Logstash → Elasticsearch pattern. 

If you want the cleanest ECK-native version, there's also an ECK Logstash CRD that can manage Logstash for you; Elastic's current quickstart explicitly supports that approach. 
