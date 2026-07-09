
The core idea

**kube-apiserver is the only component that talks to etcd.** Every other piece of Kubernetes — scheduler, controller-manager, kubelet, and anything you deploy like ingress-nginx, cert-manager, or Prometheus — is just an HTTP client of the API server. Nothing has a "back channel." This single fact explains almost everything else about how the system behaves.

```
kube-scheduler ─┐
controller-mgr ─┼──► kube-apiserver ◄──► etcd (source of truth)
cloud-ctrl-mgr ─┘         ▲
                           │  (watch)
        ┌──────────────┬──┴──────────┬──────────────┐
     kubelet      ingress-ctrl   cert-manager    prometheus
```

## What happens when you run `kubectl apply -f ingress.yaml`

This is the sequence worth knowing cold for your session, because it's also exactly the pipeline your cert-manager work plugs into:

1. **Authentication** — the API server verifies who you are (client cert, bearer token, OIDC). Output is a username + groups, nothing more.
2. **Authorization** — RBAC (or ABAC/webhook authz) checks whether that identity can perform this verb on this resource in this namespace.
3. **Mutating admission webhooks** — plugins that can *modify* the object before it's stored. Example: cert-manager's mutating webhook injects defaults into Certificate resources; sidecar injectors (like Istio) work here too.
4. **Schema validation** — the object is checked against the OpenAPI schema for that resource/version.
5. **Validating admission webhooks** — plugins that can only *accept or reject*, no modification. This is where cert-manager's validating webhook lives — it rejects malformed Certificate/Issuer objects before they ever touch etcd.
6. **Persisted to etcd** — this is the only write path. The object is now the cluster's desired state.
7. **Watch notifications fire** — every controller with an open watch connection on that resource type gets notified immediately.

Steps 3–5 are the **admission control chain**, and it's worth calling out explicitly in your session because it's the extension point most people don't know about until they've worked with cert-manager or an operator that ships CRDs — which you have.

## The watch mechanism (this is the "hood" part)

Kubernetes doesn't poll. Controllers open a long-lived HTTP connection to the API server (`GET /api/v1/pods?watch=true`) and get a stream of ADD/UPDATE/DELETE events, each tagged with a `resourceVersion`. If the connection drops, the client reconnects and resumes from its last known `resourceVersion`; if that version has been compacted out of etcd's history, it falls back to a full LIST and re-syncs.

Every controller then runs the same shape of loop:

```
observe (watch) → compare desired vs actual → act → re-observe
```

This is the **reconciliation loop**, and it's why Kubernetes is declarative rather than imperative — you're never telling it "do X," you're telling it "this is what should exist," and every controller is independently, continuously converging reality toward that.

## Tying it directly to your office work

- **Ingress controller, above/below the load balancer**: the ingress controller (e.g. ingress-nginx, or a cloud LB controller) is *itself* just a controller watching `Ingress` objects through the API server — same watch mechanism as anything else. It sits **above** the actual load balancer/proxy in the sense that it's the control-plane brain: it reads Ingress/Service/Endpoint objects and translates them into concrete proxy config (nginx.conf, or cloud LB forwarding rules via the provider's API). The load balancer itself is **below** — it's the data-plane component that actually terminates connections and moves packets/bytes. So: Ingress object → watched by ingress controller → controller renders config → pushed into the real LB/proxy → LB handles live traffic. Nothing in the data path (the LB) talks to the API server at request time — only the controller does, during reconciliation.

- **cert-manager**: it's a controller plus a set of CRDs (`Certificate`, `Issuer`, `ClusterIssuer`) plus admission webhooks. When you create a `Certificate`, cert-manager's controller watches it, drives the ACME/CA handshake, and writes the resulting cert+key into a `Secret` — which your ingress controller then watches and mounts for TLS termination. Three separate controllers, all coordinating purely by watching the same API server, no direct communication between them.

- **Prometheus**: if you're running kube-prometheus-stack, the Prometheus Operator also just watches CRDs (`ServiceMonitor`, `PodMonitor`) through the API server, and generates Prometheus's actual scrape config from them — same controller pattern again. Grafana then just talks to Prometheus's query API; it has no direct relationship to the Kubernetes API server at all.

The one framing worth leading your session with: **there is exactly one write path (through the API server into etcd) and one read pattern (watch), and every single component you work with daily — kubelet, your ingress controller, cert-manager, Prometheus operator — is just a different consumer of that same primitive.**
