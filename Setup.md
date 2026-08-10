Yep. Let's do this cleanly, and this time no giant mysterious values.yaml. We'll build it in layers and verify each layer before touching the next.

One correction to what I said earlier: for a current Elastic installation, I actually do recommend ECK even for your lab. Elastic's old standalone elasticsearch/kibana Helm charts stopped at 8.5.1, while ECK is the currently supported Kubernetes management path. 

For your one-node lab, we'll use:

1 Kubernetes node
1 Elasticsearch pod
1 Kibana pod
1 Fluent Bit pod
local-path PVC
NO Logstash
NO Lua initially
NO dynamic indices initially
NO Merge_Log initially

The target is:

Test Pod
   │
   │ stdout
   ▼
/var/log/containers/*.log
   │
   ▼
Fluent Bit
   │
   │ HTTPS
   ▼
Elasticsearch
   │
   ▼
Kibana

Fluent Bit's official Kubernetes guidance also uses a DaemonSet to collect /var/log/containers/*.log and enrich records with Kubernetes metadata. 


---

Phase 0 — Clean the old lab

Do this first.

See what currently exists:

helm list -A

Then:

kubectl get pods -A | grep -Ei 'fluent|elastic|kibana|logstash'

And:

kubectl get pvc -A

If this is genuinely a disposable logging lab, you can remove the old logging namespace:

kubectl delete namespace logging

If your old installation used another namespace, delete that namespace instead.

Then verify:

kubectl get pods -A | grep -Ei 'fluent|elastic|kibana|logstash'

Also check Helm:

helm list -A

Don't delete CRDs yet. We'll handle ECK cleanly below.


---

Phase 1 — Create our logging namespace

kubectl create namespace logging


---

Phase 2 — Install ECK

Add Elastic's official Helm repository:

helm repo add elastic https://helm.elastic.co
helm repo update

Elastic documents this repository and the eck-operator Helm chart officially. 

Install the operator:

helm upgrade --install elastic-operator \
  elastic/eck-operator \
  --namespace elastic-system \
  --create-namespace

Check:

kubectl get pods -n elastic-system

You want:

elastic-operator-xxxxx   1/1   Running

Don't proceed until that's running.


---

Phase 3 — Elasticsearch

Now create one Elasticsearch node.

Create:

cat <<'EOF' | kubectl apply -f -
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: logging
  namespace: logging
spec:
  version: 9.4.3
  nodeSets:
    - name: default
      count: 1
      config:
        node.store.allow_mmap: false
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            storageClassName: local-path
            accessModes:
              - ReadWriteOnce
            resources:
              requests:
                storage: 10Gi
EOF

I'm deliberately using 9.4.3 here rather than latest, so Elasticsearch and Kibana are pinned to the same version.

ECK's official single-node deployment follows this same basic model: one node and node.store.allow_mmap: false for a simple Kubernetes quickstart. 

Check:

kubectl get elasticsearch -n logging

Initially you may see:

HEALTH   PHASE
         ApplyingChanges

Wait:

kubectl get pods -n logging -w

Eventually:

logging-es-default-0   1/1   Running

Then:

kubectl get elasticsearch -n logging

You want:

logging   green   1   9.4.3   Ready

Check the PVC

kubectl get pvc -n logging

You should see something like:

elasticsearch-data-logging-es-default-0   Bound   10Gi   RWO   local-path

This confirms we're actually using your local-path storage.


---

Phase 4 — Test Elasticsearch BEFORE Kibana

This is important.

Don't install everything and then wonder what's broken.

Get the Elasticsearch password:

export ELASTIC_PASSWORD=$(kubectl get secret logging-es-elastic-user \
  -n logging \
  -o go-template='{{.data.elastic | base64decode}}')

Check:

echo "$ELASTIC_PASSWORD"

Now port-forward:

kubectl port-forward -n logging service/logging-es-http 9200:9200

Leave that terminal running.

Open another terminal:

curl -k -u "elastic:$ELASTIC_PASSWORD" https://localhost:9200

You should get JSON containing something like:

{
  "name": "...",
  "cluster_name": "logging",
  "version": {
    "number": "9.4.3"
  }
}

If this works:

Elasticsearch is DONE.

Don't touch Fluent Bit yet.


---

Phase 5 — Kibana

Now create Kibana:

cat <<'EOF' | kubectl apply -f -
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: logging
  namespace: logging
spec:
  version: 9.4.3
  count: 1
  elasticsearchRef:
    name: logging
EOF

This is the standard ECK pattern: Kibana references the Elasticsearch resource using elasticsearchRef. 

Check:

kubectl get kibana -n logging

And:

kubectl get pods -n logging

Wait until:

logging-kb-xxxxx   1/1   Running

Then:

kubectl port-forward -n logging service/logging-kb-http 5601:5601

Open:

https://localhost:5601

Get the password:

kubectl get secret logging-es-elastic-user \
  -n logging \
  -o=jsonpath='{.data.elastic}' | base64 --decode

ECK automatically creates the elastic credentials in a Secret. 

Login:

Username: elastic
Password: <password>

Kibana working?

Great.

At this point:

✅
         Elasticsearch
                ▲
                │
             Kibana

But there are no logs yet.


---

Phase 6 — Install Fluent Bit

Now we add the final piece.

Add the official Fluent Bit Helm repository:

helm repo add fluent https://fluent.github.io/helm-charts
helm repo update

The Fluent Bit documentation specifically recommends its official Helm chart for Kubernetes deployments. 

We're going to create a minimal configuration.

Create fluent-bit-values.yaml:

kind: DaemonSet

config:
  service: |
    [SERVICE]
        Daemon Off
        Flush 1
        Log_Level info
        Parsers_File /fluent-bit/etc/parsers.conf
        HTTP_Server On
        HTTP_Listen 0.0.0.0
        HTTP_Port 2020

  inputs: |
    [INPUT]
        Name tail
        Path /var/log/containers/*.log
        multiline.parser docker, cri
        Tag kube.*
        Mem_Buf_Limit 20MB
        Skip_Long_Lines On
        DB /var/log/flb_kubernetes.db

  filters: |
    [FILTER]
        Name kubernetes
        Match kube.*
        Merge_Log Off
        Keep_Log On

  outputs: |
    [OUTPUT]
        Name es
        Match kube.*
        Host logging-es-http.logging.svc
        Port 9200
        HTTP_User elastic
        HTTP_Passwd ${ELASTIC_PASSWORD}
        tls On
        tls.verify Off
        Suppress_Type_Name On
        Logstash_Format On
        Logstash_Prefix logstash
        Retry_Limit False

daemonSetVolumes:
  - name: varlog
    hostPath:
      path: /var/log

daemonSetVolumeMounts:
  - name: varlog
    mountPath: /var/log

env:
  - name: ELASTIC_PASSWORD
    valueFrom:
      secretKeyRef:
        name: logging-es-elastic-user
        key: elastic

Important

Notice what is NOT here:

❌ Lua
❌ custom parser
❌ namespace routing
❌ es_index
❌ Logstash_Prefix_Key
❌ XML parser
❌ JSON parser
❌ Merge_Log On
❌ complex filters

We're intentionally making Fluent Bit boring.

The official Fluent Bit Elasticsearch output supports HTTP_User, HTTP_Passwd, TLS, Logstash_Format, and indefinite retries. 

Install:

helm upgrade --install fluent-bit \
  fluent/fluent-bit \
  --namespace logging \
  --values fluent-bit-values.yaml

Check:

kubectl get pods -n logging

You should now have approximately:

logging-es-default-0       1/1 Running
logging-kb-xxxxx            1/1 Running
fluent-bit-xxxxx            1/1 Running

Because Fluent Bit is a DaemonSet, one pod is exactly what we expect on your one-node cluster. 


---

Phase 7 — Don't test with your real application yet

Let's use a ridiculously simple test.

kubectl create namespace logging-test

Create:

cat <<'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-generator
  namespace: logging-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: log-generator
  template:
    metadata:
      labels:
        app: log-generator
    spec:
      containers:
        - name: logger
          image: busybox:1.36
          command:
            - sh
            - -c
            - |
              i=0
              while true; do
                echo "HELLO FROM LOGGING TEST - message=$i namespace=logging-test"
                i=$((i+1))
                sleep 2
              done
EOF

Check:

kubectl logs -n logging-test deployment/log-generator

You should see:

HELLO FROM LOGGING TEST - message=0 namespace=logging-test
HELLO FROM LOGGING TEST - message=1 namespace=logging-test
HELLO FROM LOGGING TEST - message=2 namespace=logging-test


---

Phase 8 — Check Fluent Bit

kubectl logs -n logging -l app.kubernetes.io/name=fluent-bit --tail=100

You should not see:

failed to flush chunk
retrying

If you do, STOP HERE.

Don't touch Kibana.

We troubleshoot Fluent Bit → Elasticsearch.


---

Phase 9 — Check Elasticsearch

Port-forward is already available if you left it running:

curl -k -u "elastic:$ELASTIC_PASSWORD" \
  "https://localhost:9200/_cat/indices?v"

You should see something resembling:

health status index
green  open   logstash-2026.08.10

Then:

curl -k -u "elastic:$ELASTIC_PASSWORD" \
  "https://localhost:9200/logstash-*/_search?pretty"

You should find:

HELLO FROM LOGGING TEST

If you see that:

🎉 Fluent Bit → Elasticsearch works.


---

Phase 10 — Kibana

Go to Kibana:

https://localhost:5601

Create a Data View:

logstash-*

Use:

@timestamp

as the time field.

Search:

namespace_name : "logging-test"

You should see the messages.


---

Phase 11 — NOW test your real application

Only now deploy your actual application.

And don't modify Fluent Bit.

Your application can produce:

JSON
XML
<entry>
   ...
</entry>

etc.

With:

Merge_Log Off
Keep_Log On

Fluent Bit will initially treat the application payload as a log value rather than trying to merge it into the Kubernetes record.

That is exactly what we want for the first test.

If:

kubectl logs
       ↓
Fluent Bit
       ↓
Elasticsearch
       ↓
Kibana

works for the simple test but fails for your application, then we know the problem is actually associated with your application's log records.

That's a dramatically better debugging position than where we are now.


---

After everything works: namespace indices

Only then do we add your requirement:

abhishek-namespace-a-2026.08.10
abhishek-namespace-b-2026.08.10
abhishek-namespace-c-2026.08.10

And we don't even need your Lua script necessarily.

Fluent Bit's Elasticsearch output supports:

Logstash_Prefix_Key

which can use a record field such as kubernetes.namespace_name to determine the index prefix. 

So we can eventually do:

Logstash_Format On
Logstash_Prefix logstash
Logstash_Prefix_Key kubernetes['namespace_name']

rather than maintaining Lua just to construct an index name.

But don't add this yet.


---

Complete uninstall

This is the other thing you specifically asked for.

When you want to destroy the lab:

1. Remove Fluent Bit

helm uninstall fluent-bit -n logging

2. Remove Kibana

kubectl delete kibana logging -n logging

3. Remove Elasticsearch

kubectl delete elasticsearch logging -n logging

Wait:

kubectl get pods -n logging

Then remove the PVC:

kubectl delete pvc -n logging --all

Because you're using local-path, deleting the PVC is important if you want a genuinely fresh Elasticsearch installation.

4. Remove ECK

helm uninstall elastic-operator -n elastic-system

Then:

kubectl delete namespace elastic-system

For a completely disposable lab, you can then remove ECK CRDs:

kubectl get crd | grep k8s.elastic.co

and delete the ECK CRDs if you're sure no other Elastic workloads use them.

5. Remove logging namespace

kubectl delete namespace logging
kubectl delete namespace logging-test


---

One important change from your previous setup

Your old configuration had:

Fluent Bit
   ↓
Kubernetes filter
   ↓
Lua
   ↓
dynamic es_index
   ↓
Logstash_Format
   ↓
Elasticsearch

We're going to establish:

Fluent Bit
   ↓
Kubernetes filter
   ↓
Elasticsearch

First.

Then:

working pipeline
       ↓
namespace indices
       ↓
multiline
       ↓
application-specific parsing

one piece at a time.

That way, if "failed to flush chunk" comes back, we know exactly which change introduced it instead of spending another three days playing Helm-config whack-a-mole.

One prerequisite

Before you execute Phase 2, check:

kubectl version
helm version
kubectl get storageclass

Your local-path should show as the available StorageClass. Also make sure the single node has roughly 2 GiB or more of free memory for Elasticsearch; Elastic explicitly notes that insufficient free memory can leave a one-node Elasticsearch pod Pending. 

If those checks are fine, start at Phase 0 and do this sequentially. Don't jump ahead.
