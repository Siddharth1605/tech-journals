Good — let's build this practically in K8s now. I'll walk you through verification at every stage so you know exactly what to check.

---

## Overall Flow You're Building

```
cert-manager generates cert → stores in K8s Secret
                ↓
Your Pod mounts that Secret as a volume
                ↓
An initContainer converts PEM (tls.crt/tls.key) to PKCS12
                ↓
Jetty reads the PKCS12 keystore on startup
                ↓
Jetty serves HTTPS using that cert
```

---

## Step 1 — Confirm cert-manager Is Actually Running

```bash
kubectl get pods -n cert-manager
```

You should see 3 pods, all `Running`:
```
cert-manager-xxx
cert-manager-cainjector-xxx
cert-manager-webhook-xxx
```

If any are not Running, stop here and check:
```bash
kubectl describe pod <pod-name> -n cert-manager
kubectl logs <pod-name> -n cert-manager
```

---

## Step 2 — Apply ClusterIssuer and Check It's Ready

```bash
kubectl apply -f selfsigned-issuer.yaml

kubectl get clusterissuer
```

Expected output:
```
NAME                  READY   AGE
selfsigned-issuer     True    10s
```

If `READY` is `False`:
```bash
kubectl describe clusterissuer selfsigned-issuer
# Look at Events section at bottom for the actual error
```

---

## Step 3 — Apply Certificate and Watch It Get Issued

```bash
kubectl apply -f certificate.yaml
```

```bash
# Watch in real time
kubectl get certificate -w
```

You'll see it transition:
```
NAME         READY   SECRET              AGE
jetty-tls    False   jetty-tls-secret    2s
jetty-tls    True    jetty-tls-secret    8s   ← wait for this
```

If it stays `False` for long or shows error:
```bash
kubectl describe certificate jetty-tls

# Look for Events at the bottom — common issues:
# - Issuer not found
# - CertificateRequest failed
```

Also check the intermediate object cert-manager creates:
```bash
kubectl get certificaterequest
kubectl describe certificaterequest <name>
```

---

## Step 4 — Verify the Secret Was Actually Created Correctly

```bash
kubectl get secret jetty-tls-secret -o yaml
```

You should see:
```yaml
apiVersion: v1
kind: Secret
type: kubernetes.io/tls
data:
  tls.crt: <base64 string>
  tls.key: <base64 string>
```

**Decode and inspect the actual certificate** — this is important, don't just trust it exists:

```bash
kubectl get secret jetty-tls-secret -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/tls.crt

# Inspect the cert
openssl x509 -in /tmp/tls.crt -text -noout
```

Check specifically:
```
Subject: CN = your-app.local        ← matches what you defined
Validity:
    Not Before: ...
    Not After:  ...                  ← confirms expiry, usually 90 days default
Issuer: CN = your-app.local          ← self-signed, so issuer = subject
```

If this looks correct — cert-manager part is verified working.

---

## Step 5 — Set Up the initContainer to Convert PEM to PKCS12

This is the part that often trips people up. Your Pod spec needs an initContainer because Jetty wants PKCS12, but the Secret gives you raw PEM.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jetty-app
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
        image: alpine/openssl
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
        - name: keystore
          mountPath: /keystore

      containers:
      - name: jetty
        image: your-jetty-image
        volumeMounts:
        - name: keystore
          mountPath: /etc/jetty/keystore
        ports:
        - containerPort: 8443

      volumes:
      - name: tls-secret
        secret:
          secretName: jetty-tls-secret
      - name: keystore
        emptyDir: {}
```

What's happening:
```
tls-secret volume → mounts the raw cert-manager Secret (tls.crt, tls.key)
keystore volume    → emptyDir, shared between initContainer and main container
initContainer      → converts PEM to PKCS12, writes to shared emptyDir
main container     → reads the converted keystore.p12 from shared volume
```

---

## Step 6 — Verify the Conversion Actually Happened

```bash
kubectl apply -f deployment.yaml

kubectl get pods
```

Check initContainer logs:
```bash
kubectl logs <pod-name> -c convert-cert
```

Should show no errors (openssl is usually silent on success).

Check the file actually exists in the running Pod:
```bash
kubectl exec -it <pod-name> -c jetty -- ls -la /etc/jetty/keystore/
```

Should show:
```
keystore.p12
```

---

## Step 7 — Verify Jetty Actually Started With SSL

```bash
kubectl logs <pod-name> -c jetty
```

Look for lines indicating SSL connector started, something like:
```
Started ServerConnector@...{SSL, (ssl, http/1.1)}{0.0.0.0:8443}
```

If Jetty crashed on startup, check for keystore password mismatch or path errors in the logs.

---

## Step 8 — Test the HTTPS Connection From Inside the Cluster

```bash
kubectl run test-curl --image=curlimages/curl -it --rm -- sh

# Inside that pod:
curl -k https://jetty-app.default.svc.cluster.local:8443
```

`-k` skips cert verification since it's self-signed and the test pod doesn't have the CA in its trust store. You should get a response (even an error response from your app is fine — it proves TLS handshake succeeded, not that your app logic works).

---

## Step 9 — Verify The Actual TLS Handshake Properly

This is the real proof — checking the certificate presented during handshake matches what cert-manager issued:

```bash
kubectl run test-openssl --image=alpine/openssl -it --rm -- sh

# Inside:
openssl s_client -connect jetty-app.default.svc.cluster.local:8443 -showcerts
```

Check output for:
```
subject=CN = your-app.local      ← matches your Certificate spec
issuer=CN = your-app.local       ← self-signed
Verify return code: 18 (self-signed certificate)   ← expected for self-signed
```

If you see the handshake complete and certificate details matching — **end to end verification is done.**

---

## Checklist Summary

```
[ ] cert-manager pods running
[ ] ClusterIssuer shows READY=True
[ ] Certificate shows READY=True  
[ ] Secret contains tls.crt and tls.key
[ ] openssl x509 shows correct CN and validity dates
[ ] initContainer logs show no errors
[ ] keystore.p12 file exists in running Pod
[ ] Jetty logs show SSL connector started
[ ] curl -k from another pod gets a response
[ ] openssl s_client shows correct cert details in handshake
```

---

## One Thing to Add to Your PoC Findings

```
Observation: cert-manager Secret only contains PEM files.
Java/Jetty needs PKCS12 or JKS. This conversion step is not 
automatic and requires either:
  a) initContainer doing openssl conversion on every Pod start
  b) A sidecar that watches Secret changes and reconverts on renewal
  
Without (b), cert renewal by cert-manager updates the Secret 
but Jetty keeps running with the OLD keystore until Pod restarts.
This means you need something like Reloader (stakater/reloader) 
to trigger a rolling restart when the Secret changes.
```

Try this end to end and tell me where you get stuck — likely spots are either the ClusterIssuer not being ready, or the initContainer volume mounting.
