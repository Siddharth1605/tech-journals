
```text
Certificate expired
        ↓
Postman / curl (with CA validation)
        ↓
Certificate has expired error
        ↓
Pod restart
        ↓
Jetty loads renewed keystore.p12
        ↓
HTTPS works again
```

The next step is to automate that restart using **Stakater Reloader**.

## Why Reloader?

Current behavior:

```text
cert-manager renews certificate
        ↓
Updates Secret (nexus-tls)
        ↓
Jetty still serves old certificate
        ↓
Manual pod restart required
```

Desired behavior:

```text
cert-manager renews certificate
        ↓
Updates Secret
        ↓
Reloader detects Secret update
        ↓
Deployment restarted automatically
        ↓
Jetty loads new certificate
```

***

## Install Reloader

If Helm is available:

```bash
helm repo add stakater https://stakater.github.io/stakater-charts
helm repo update

helm install reloader stakater/reloader \
  -n reloader-system \
  --create-namespace
```

Verify:

```bash
kubectl get pods -n reloader-system
```

Expected:

```text
reloader-xxxx Running
```

***

## Update Deployment

Add annotation:

```yaml
metadata:
  annotations:
    reloader.stakater.com/auto: "true"
```

Example:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nexus
  annotations:
    reloader.stakater.com/auto: "true"
```

Apply:

```bash
kubectl apply -f deployment.yaml
```

***

## More Specific Option

Instead of monitoring everything:

```yaml
metadata:
  annotations:
    secret.reloader.stakater.com/reload: "nexus-tls,keystore-password"
```

This means:

```text
Restart only when:
 - nexus-tls changes
 - keystore-password changes
```

***

## Test It

Force certificate re-issuance:

```bash
kubectl delete secret nexus-tls
```

or modify the Certificate resource.

Watch:

```bash
kubectl get pods -w
```

Expected:

```text
Secret updated
      ↓
Reloader detects change
      ↓
New ReplicaSet created
      ↓
Old Pod terminated
      ↓
New Pod started
```

Check logs:

```bash
kubectl logs -n reloader-system deploy/reloader
```

You'll see messages similar to:

```text
Secret nexus-tls updated
Reloading Deployment nexus
```

***

## Architecture for Document

```text
cert-manager
      ↓
Certificate Renewal
      ↓
Update Secret (nexus-tls)
      ↓
Stakater Reloader
      ↓
Automatic Deployment Restart
      ↓
Jetty loads renewed keystore.p12
      ↓
HTTPS continues without manual intervention
```

### Recommended Conclusion

> Jetty does not automatically switch to the renewed certificate present in the updated Kubernetes Secret. Stakater Reloader can be used to monitor certificate Secret changes and automatically restart the application pod, ensuring that renewed certificates are picked up without manual intervention.
