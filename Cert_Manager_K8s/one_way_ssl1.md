
Below is a complete one-way SSL flow using **cert-manager + Jetty + Kubernetes Secrets**.

***

# Architecture Overview

```text
                    ┌──────────────────┐
                    │ selfsigned-root  │
                    └─────────┬────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ root-ca          │
                    │ Certificate      │
                    └─────────┬────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ root-ca-secret   │
                    │ tls.crt          │
                    │ tls.key          │
                    └─────────┬────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ internal-ca      │
                    │ ClusterIssuer    │
                    └─────────┬────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ nexus-cert │
                    │ Certificate      │
                    └─────────┬────────┘
                              │
                              ▼
                    ┌────────────────────────┐
                    │ nexus-tls        │
                    │ tls.crt                │
                    │ tls.key                │
                    │ ca.crt                 │
                    │ keystore.p12           │
                    └─────────┬──────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Kubernetes Pod   │
                    └─────────┬────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ Jetty 12         │
                    │ HTTPS Enabled    │
                    └──────────────────┘
```

***

# Step 1 - Create Root Bootstrap Issuer

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-root
spec:
  selfSigned: {}
```

Apply:

```bash
kubectl apply -f selfsigned-root.yaml
```

Verify:

```bash
kubectl get clusterissuer
```

Expected:

```text
selfsigned-root   True
```

***

# Step 2 - Create Root CA

Equivalent to:

```bash
openssl genrsa -des3 -out cakey.pem
openssl req -new -x509 ...
```

Kubernetes version:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: root-ca
  namespace: cert-manager
spec:
  isCA: true

  commonName: root-ca

  secretName: root-ca-secret

  issuerRef:
    name: selfsigned-root
    kind: ClusterIssuer
```

Apply:

```bash
kubectl apply -f root-ca.yaml
```

Verify:

```bash
kubectl get certificate -n cert-manager
```

Expected:

```text
root-ca   True
```

***

# Step 3 - Create Internal CA Issuer

Equivalent to:

```text
cakey.pem
cacert.pem
```

used to sign server certificates.

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: internal-ca
spec:
  ca:
    secretName: root-ca-secret
```

Apply:

```bash
kubectl apply -f internal-ca.yaml
```

Verify:

```bash
kubectl get clusterissuer internal-ca
```

Expected:

```text
internal-ca   True
```

***

# Step 4 - Create PKCS12 Password Secret

This is the step that was missing.

In your old OpenSSL flow:

```bash
openssl pkcs12 -export
```

prompted for:

```text
Export Password:
```

In Kubernetes we store that password in a Secret.

Create:

```bash
kubectl create secret generic keystore-password \
  --from-literal=password=MyStrongPassword123
```

Verify:

```bash
kubectl get secret keystore-password
```

***

# Step 5 - Create Server Certificate

Equivalent to:

```bash
openssl genrsa
openssl req
openssl x509
openssl pkcs12 -export
```

all automated by cert-manager:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: nexus-cert
spec:
  secretName: nexus-tls

  duration: 365d

  renewBefore: 30d

  commonName: nexus

  dnsNames:
    - nexus
    - nexus.default
    - nexus.default.svc
    - nexus.default.svc.cluster.local

  ipAddresses:
    - x.x.x.x

  issuerRef:
    name: internal-ca
    kind: ClusterIssuer

  privateKey:
    algorithm: RSA
    size: 4096

  keystores:
    pkcs12:
      create: true

      passwordSecretRef:
        name: keystore-password
        key: password
```

Apply:

```bash
kubectl apply -f nexus-cert.yaml
```

Verify:

```bash
kubectl get certificate
```

Expected:

```text
nexus-cert   True
```

***

# Step 6 - Check Generated Secret

```bash
kubectl get secret nexus-tls
```

Verify contents:

```bash
kubectl get secret nexus-tls \
-o jsonpath='{.data}' | jq 'keys'
```

Expected:

```text
[
  "tls.crt",
  "tls.key",
  "ca.crt",
  "keystore.p12"
]
```

Meaning:

| Old Manual File | cert-manager |
| --------------- | ------------ |
| nexus-server.cert.pem    | tls.crt      |
| nexus-server.key.pem     | tls.key      |
| cacert.pem      | ca.crt       |
| keystore.p12    | keystore.p12 |

***

# Step 7 - Mount Secret into Pod

Deployment:

```yaml
volumes:
- name: tls-certs
  secret:
    secretName: nexus-tls
```

Mount:

```yaml
volumeMounts:
- name: tls-certs
  mountPath: nexus/webserver/etc
  readOnly: true
```

Inside pod:

```text
nexus/webserver/etc/

tls.crt
tls.key
ca.crt
keystore.p12
```

***

# Step 8 - Pass Password to Jetty

Create environment variable from Secret:

```yaml
env:
- name: KEYSTORE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: keystore-password
      key: password
```

***

# Step 9 - Start Java with System Properties

You discovered that Jetty was reading JVM properties rather than environment variables.

Correct:

```bash
java \
-Djetty.sslContext.keyStorePassword=$KEYSTORE_PASSWORD \
-Djetty.sslContext.keyManagerPassword=$KEYSTORE_PASSWORD \
-jar app.jar
```

or:

```bash
JAVA_OPTS="
-Djetty.sslContext.keyStorePassword=$KEYSTORE_PASSWORD
-Djetty.sslContext.keyManagerPassword=$KEYSTORE_PASSWORD
"
```

***

# Step 10 - ssl.ini

```properties
jetty.sslContext.keyStorePath=nexus/webserver/etc/keystore.p12

jetty.sslContext.keyStoreType=PKCS12

jetty.sslContext.keyStorePassword=${jetty.sslContext.keyStorePassword}

jetty.sslContext.keyManagerPassword=${jetty.sslContext.keyManagerPassword}
```

Or simply omit them from `ssl.ini` if they are already provided via JVM properties.

***

# Step 11 - Verify Password

Inside pod:

```bash
keytool -list \
-storetype PKCS12 \
-keystore nexus/webserver/etc/keystore.p12 \
-storepass "$KEYSTORE_PASSWORD"
```

Expected:

```text
Your keystore contains 1 entry
```

***

# Step 12 - Verify HTTPS

```bash
curl -vk \
https://x.x.x.x:30005/nexus-webservice/services/status
```

If the IP is included in:

```yaml
ipAddresses:
  - x.x.x.x
```

the SNI validation will succeed and Jetty will return the API response.

***

# Password Flow Summary

```text
keystore-password Secret
      │
      ▼
password=MyStrongPassword123
      │
      ▼
Kubernetes Env Variable
KEYSTORE_PASSWORD
      │
      ▼
Java JVM Startup
-Djetty.sslContext.keyStorePassword=
-Djetty.sslContext.keyManagerPassword=
      │
      ▼
Jetty
      │
      ▼
Decrypt keystore.p12
      │
      ▼
HTTPS Starts Successfully
```

The biggest lessons from your implementation were:

1. `root-ca-secret` had to exist before `internal-ca` could become Ready.
2. The external IP used by clients (`x.x.x.x`) had to be added under `ipAddresses`.
3. Jetty 12 did **not** automatically resolve Kubernetes environment variables inside `ssl.ini`; the password had to be passed as JVM `-D` system properties.
4. The PKCS12 password must be the same in:
   * `keystore-password` Secret
   * `Certificate.keystores.pkcs12.passwordSecretRef`
   * Jetty JVM startup parameters.
