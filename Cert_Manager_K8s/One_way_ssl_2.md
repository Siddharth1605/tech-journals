You're right — let me give you the actual cert-manager YAML files explicitly, since I referenced them but never wrote them out.

---

## File 1 — Install cert-manager

This is not a YAML you write — it's the official release manifest you apply directly:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.0/cert-manager.yaml
```

This single command installs cert-manager's CRDs (Custom Resource Definitions) and all its controller Pods. You don't write this file yourself — it comes from cert-manager's official release.

Verify:
```bash
kubectl get pods -n cert-manager
```

```
NAME                                       READY   STATUS    AGE
cert-manager-7d...                         1/1     Running   30s
cert-manager-cainjector-6c...              1/1     Running   30s
cert-manager-webhook-8f...                 1/1     Running   30s
```

---

## File 2 — ClusterIssuer (selfsigned-issuer.yaml)

Create this file yourself:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
spec:
  selfSigned: {}
```

Apply it:
```bash
kubectl apply -f selfsigned-issuer.yaml
```

Verify:
```bash
kubectl get clusterissuer

NAME                  READY   AGE
selfsigned-issuer     True    5s
```

---

## File 3 — Certificate (certificate.yaml)

Create this file:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: jetty-tls
  namespace: default
spec:
  secretName: jetty-tls-secret
  issuerRef:
    name: selfsigned-issuer
    kind: ClusterIssuer
  commonName: jetty-app.local
  dnsNames:
  - jetty-app.local
  - jetty-app.default.svc.cluster.local
  duration: 2160h        # 90 days
  renewBefore: 360h       # renew 15 days before expiry
```

Apply it:
```bash
kubectl apply -f certificate.yaml
```

Verify:
```bash
kubectl get certificate

NAME         READY   SECRET              AGE
jetty-tls    True    jetty-tls-secret    10s
```

If it's stuck on `False`, debug with:
```bash
kubectl describe certificate jetty-tls
```

---

## File 4 — Confirm the Secret cert-manager Created

You don't write this file — cert-manager creates it automatically based on File 3. Just verify it:

```bash
kubectl get secret jetty-tls-secret -o yaml
```

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: jetty-tls-secret
  namespace: default
type: kubernetes.io/tls
data:
  tls.crt: <long base64 string>
  tls.key: <long base64 string>
  ca.crt: <long base64 string>
```

Decode and inspect:
```bash
kubectl get secret jetty-tls-secret -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/tls.crt
openssl x509 -in /tmp/tls.crt -text -noout
```

---

## File 5 — Deployment with initContainer (deployment.yaml)

This is the main file connecting everything together:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jetty-app
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jetty-app
  template:
    metadata:
      labels:
        app: jetty-app
    spec:
      initContainers:
      - name: convert-cert
        image: alpine/openssl:latest
        command:
        - sh
        - -c
        - |
          openssl pkcs12 -export \
            -in /tls/tls.crt \
            -inkey /tls/tls.key \
            -out /keystore/keystore.p12 \
            -name jetty \
            -password pass:changeit
        volumeMounts:
        - name: tls-secret
          mountPath: /tls
          readOnly: true
        - name: keystore
          mountPath: /keystore

      containers:
      - name: jetty
        image: your-jetty-image:latest
        ports:
        - containerPort: 8443
          name: https
        volumeMounts:
        - name: keystore
          mountPath: /etc/jetty/keystore
          readOnly: true
        env:
        - name: KEYSTORE_PATH
          value: /etc/jetty/keystore/keystore.p12
        - name: KEYSTORE_PASSWORD
          value: changeit

      volumes:
      - name: tls-secret
        secret:
          secretName: jetty-tls-secret
      - name: keystore
        emptyDir: {}
```

Apply it:
```bash
kubectl apply -f deployment.yaml
```

Verify Pod is running:
```bash
kubectl get pods

NAME                         READY   STATUS    AGE
jetty-app-7d8f9c-xk2p9       1/1     Running   20s
```

---

## File 6 — Service (service.yaml)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: jetty-app
  namespace: default
spec:
  selector:
    app: jetty-app
  ports:
  - port: 8443
    targetPort: 8443
    name: https
  type: ClusterIP
```

Apply it:
```bash
kubectl apply -f service.yaml
```

Verify:
```bash
kubectl get svc jetty-app
```

---

## Verification Sequence — Run These In Order

**1. Check initContainer ran successfully:**
```bash
kubectl logs jetty-app-7d8f9c-xk2p9 -c convert-cert
```
No output = success (openssl is silent unless error).

**2. Check keystore file exists in the Pod:**
```bash
kubectl exec -it jetty-app-7d8f9c-xk2p9 -c jetty -- ls -la /etc/jetty/keystore/
```
Should show `keystore.p12`.

**3. Check Jetty container logs for SSL startup:**
```bash
kubectl logs jetty-app-7d8f9c-xk2p9 -c jetty
```
Look for SSL connector started message.

**4. Test from inside cluster:**
```bash
kubectl run test-curl --image=curlimages/curl -it --rm -- \
  curl -k https://jetty-app.default.svc.cluster.local:8443
```

**5. Inspect actual TLS handshake:**
```bash
kubectl run test-ssl --image=alpine/openssl -it --rm -- \
  openssl s_client -connect jetty-app.default.svc.cluster.local:8443 -showcerts
```

Look for:
```
subject=CN = jetty-app.local
issuer=CN = jetty-app.local
Verify return code: 18 (self-signed certificate)
```

---

## Complete File List Summary

```
selfsigned-issuer.yaml   → defines WHO signs certs
certificate.yaml          → requests a cert for your app
                            (cert-manager auto-creates jetty-tls-secret)
deployment.yaml            → runs Jetty, converts PEM→PKCS12 via initContainer
service.yaml                → exposes Jetty inside cluster
```

Apply order matters:
```bash
kubectl apply -f selfsigned-issuer.yaml
kubectl apply -f certificate.yaml
# wait for certificate READY=True
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

Try this end to end now. Tell me exactly which step fails if something breaks — share the `kubectl describe` or `kubectl logs` output at that point.
