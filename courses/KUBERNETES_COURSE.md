# python_nutshell: Kubernetes learning course

You already know Docker and use it here: `fast_api/Dockerfile` plus a `docker-compose.yml` with `postgres` (pgvector), `redis`, `mcp-server`, `api` and an optional `ollama`. This course teaches Kubernetes from zero, using **that same stack** as the running example. By the end you will run the whole app on a local cluster, then on production-style patterns (Helm, autoscaling, security, GitOps).

## How to use this file

1. Chapters are in **study order**. Each lists what it **Needs**.
2. Ask: *"Tailor a lesson for Chapter N."* A lesson is then written against your actual repo (real manifests for `api`, `postgres`, `redis`, ...).
3. **You write the code yourself.** Claude does not edit the repo for the Lab items. For each lesson Claude gives you a step-by-step guide: which file to create or change (full path), the exact code to type, and the command to run after each step.
4. Tick **Done when** only once you can explain what you typed.

Each chapter has: **Needs**, **Why**, **Compose → K8s** (how it maps to what you know), **Learn**, **Lab**, **Done when**.

**Working agreement.**
- Every lesson is a numbered list of steps. Each step names the **file path**, whether to **create** or **update** it, the **code** (with the changed lines marked when updating), and a **verify** command with the expected output.
- Claude explains every non-obvious field in the code, so you type it knowing why.
- Claude gives you the commands for risky actions (`delete ns`, `drain`, deleting PVCs) with a warning, and you decide when to run them.
- Each lesson ends with an "explain it back" check and a "break it on purpose" exercise.
- If you paste an error or `kubectl describe` output, Claude helps you debug it; Claude edits repo files only if you explicitly ask.

## Setup: what you need on your machine

You have Rancher Desktop. Already detected on this machine: Docker `29.0.2-rd`, `kubectl v1.35.0`, `helm v3.19.1`, Kustomize `v5.7.1`. So the core is **done**.

**Rancher Desktop settings to check** (Preferences):
- **Container Engine = dockerd (moby)**. Then `docker build` images are directly visible to the cluster, no registry needed. (If you pick containerd, use `nerdctl` and `--namespace k8s.io` instead.)
- **Kubernetes enabled** (it runs k3s). Give it at least **4 CPU / 8 GB RAM** (Ollama and Postgres are hungry; 2 GB will make pods crash for confusing reasons).
- **Traefik** ingress ships enabled with k3s. Keep it on; Chapter 9 uses it.

**Install later, only when a chapter asks** (all optional until then):

| Tool | Chapter | Why | Install (PowerShell) |
|---|---|---|---|
| `k9s` | 3+ | Terminal UI for the cluster, saves typing | `winget install Derailed.k9s` |
| `kubectx` / `kubens` | 4+ | Switch context / namespace fast | `winget install ahmetb.kubectx` |
| `stern` | 7+ | Tail logs across many pods | `winget install stern.stern` |
| `kubeconform` | 14 | Validate manifests offline | `winget install yannh.kubeconform` |
| `kind` or `minikube` | 20 | A second, multi-node cluster to test scheduling | `winget install Kubernetes.kind` |
| Argo CD (in-cluster) | 22 | GitOps | installed with `kubectl`, not on host |
| VS Code **Kubernetes** + **YAML** extensions | 1+ | Schema hints, autocomplete | VS Code marketplace |

**Verify now:**

```powershell
kubectl config current-context        # should print: rancher-desktop
kubectl get nodes                     # one node, STATUS Ready
kubectl get pods -A                   # kube-system pods Running (coredns, traefik, ...)
```

If `kubectl get nodes` fails, Rancher Desktop's Kubernetes is not running; start it in the UI and wait for the green status.

**Habit that saves you:** `kubectl config get-contexts` before every destructive command. You can have a work cluster in the same kubeconfig.

## The one-picture map

| Layer | Question | Objects | Chapters |
|---|---|---|---|
| **Run** | How do containers run? | Pod, ReplicaSet, Deployment, Job, CronJob | 3, 4, 8 |
| **Connect** | How do they find each other and the outside? | Service, DNS, Ingress, NetworkPolicy | 5, 9, 17 |
| **Configure** | Where do settings, secrets and data live? | ConfigMap, Secret, Volume, PV/PVC, StatefulSet | 6, 7, 10, 11 |
| **Operate** | Is it healthy, scaled, safe? | probes, resources, RBAC, observability, HPA | 12, 13, 16, 18, 19 |
| **Ship** | How do changes reach the cluster? | Kustomize, Helm, CI/CD, GitOps | 14, 15, 21, 22 |
| **Cloud (EKS)** | How does this run on AWS? | VPC, IAM, ALB, EBS, IRSA, Karpenter | 23 to 28 |

## Compose → Kubernetes cheat sheet

| Docker Compose (what you have) | Kubernetes equivalent |
|---|---|
| `services.api` | `Deployment` + `Service` |
| `image:` / `build:` | `image:` (no `build`; you build and push/load beforehand) |
| `ports: "8000:8000"` | `Service` port, plus `Ingress` or `port-forward` for outside access |
| `environment:` / `env_file: .env` | `ConfigMap` (plain) / `Secret` (sensitive), via `envFrom` |
| `volumes: postgres_data:` | `PersistentVolumeClaim` (or `StatefulSet` `volumeClaimTemplates`) |
| `volumes: ./:/app` (bind mount) | No real equivalent. Bake code into the image; use Skaffold/Tilt for dev loops |
| `depends_on: condition: service_healthy` | `readinessProbe` + `initContainers` (no ordering guarantee otherwise) |
| `healthcheck:` | `livenessProbe` / `readinessProbe` / `startupProbe` |
| `restart: unless-stopped` | Built in: Deployments always restart failed pods |
| `profiles: ["ollama"]` | Separate manifest/Helm value/Kustomize overlay, or replicas `0` |
| service name as hostname (`postgres`) | Service DNS: `postgres.<namespace>.svc.cluster.local` (just `postgres` in the same namespace) |
| `ollama-pull` one-shot service | `Job` (or `initContainer`) |

---

## Chapter tracker

| # | Chapter | Level | Done |
|---|---|---|---|
| 1 | Why Kubernetes, and the mental model | Basic | [x] |
| 2 | Your local cluster and kubectl fluency | Basic | [x] |
| 3 | Pods | Basic | [x] |
| 4 | Deployments, ReplicaSets, rollouts | Basic | [ ] |
| 5 | Services and DNS | Basic | [ ] |
| 6 | ConfigMaps and Secrets | Basic | [ ] |
| 7 | Storage: volumes, PV, PVC | Intermediate | [ ] |
| 8 | Jobs and CronJobs | Intermediate | [ ] |
| 9 | Ingress | Intermediate | [ ] |
| 10 | StatefulSets: running Postgres and Redis | Intermediate | [ ] |
| 11 | Deploy the whole python_nutshell stack | Intermediate | [ ] |
| 12 | Health probes and the pod lifecycle | Intermediate | [ ] |
| 13 | Resources, QoS, scheduling | Intermediate | [ ] |
| 14 | Kustomize and manifest hygiene | Intermediate | [ ] |
| 15 | Helm | Intermediate | [ ] |
| 16 | RBAC and ServiceAccounts | Advanced | [ ] |
| 17 | NetworkPolicy and pod security | Advanced | [ ] |
| 18 | Observability: logs, metrics, tracing | Advanced | [ ] |
| 19 | Autoscaling: HPA, VPA, KEDA | Advanced | [ ] |
| 20 | Cluster internals and troubleshooting | Advanced | [ ] |
| 21 | CI/CD to Kubernetes | Advanced | [ ] |
| 22 | GitOps with Argo CD | Advanced | [ ] |
| 23 | AWS foundations for EKS (no account needed) | EKS | [ ] |
| 24 | EKS clusters: eksctl and Terraform | EKS | [ ] |
| 25 | EKS networking: VPC CNI, load balancers, ingress | EKS | [ ] |
| 26 | EKS identity and storage: IRSA / Pod Identity, EBS, EFS | EKS | [ ] |
| 27 | EKS operations: nodes, Karpenter, upgrades, observability | EKS | [ ] |
| 28 | Run python_nutshell on EKS, and cost control | EKS | [ ] |
| 29 | Operators, CRDs, extending Kubernetes | Expert | [ ] |
| 30 | Service mesh, GPUs for Ollama, cloud, certification | Expert | [ ] |

**Study order, and why it is in this order:**

| Stage | Chapters | What you can do after it |
|---|---|---|
| 1. Core objects | 1 to 6 | Run, expose and configure a container in a cluster |
| 2. State and traffic | 7 to 10 | Keep data, run jobs, route outside traffic, run Postgres/Redis |
| 3. Your app on Kubernetes | 11 | The whole python_nutshell stack works (first milestone) |
| 4. Make it solid | 12 to 13 | Probes, graceful rollouts, resource limits |
| 5. Package it | 14 to 15 | Kustomize overlays, then Helm (needed to install most tools below) |
| 6. Secure and see it | 16 to 18 | RBAC, network policy, logs/metrics/tracing |
| 7. Scale and fix it | 19 to 20 | Autoscaling (uses the metrics from 18), troubleshooting |
| 8. Ship it | 21 to 22 | CI/CD, then GitOps |
| 9. Run it on AWS | 23 to 28 | EKS, in stages that work without an account (see Part D intro) |
| 10. Expert depth | 29 to 30 | Operators, service mesh, GPUs, certification |

Dependency rules used for the order: a chapter never uses a tool taught later (Helm at 15 comes before the Helm-installed Prometheus at 18 and KEDA at 19; metrics at 18 come before custom-metric autoscaling at 19; CI/CD at 21 comes before GitOps at 22; EKS comes after all of them because it reuses every one).

Suggested path: **1 → 11** gets your app running (about 2 weeks part time). **12 → 15** makes it solid and packaged. **16 → 22** makes it production-grade. **23 → 28** is EKS (see "Learning EKS without an AWS account" in Part D). **29, 30** are optional depth.

---

# Part A: Basics

## Chapter 1: Why Kubernetes, and the mental model

**Needs:** Docker knowledge (you have it).

**Why.** Compose runs containers on **one machine**. Kubernetes runs them across **many machines** and keeps them in a **declared state**: self-healing, scaling, rolling updates, service discovery. Without the model, every later object looks arbitrary.

**Compose → K8s.** Compose is imperative-ish ("start these"). Kubernetes is **declarative**: you write the *desired state* in YAML, controllers loop forever making *actual state* match.

**Learn.**
- Control plane (API server, etcd, scheduler, controller manager) vs worker nodes (kubelet, container runtime, kube-proxy)
- The **reconciliation loop**: desired vs actual, the idea behind everything
- Declarative YAML: `apiVersion`, `kind`, `metadata`, `spec`, `status`
- Objects are stored in etcd, all access goes through the API server
- Namespaces, labels, selectors, annotations
- When you do *not* need Kubernetes (single VM, Compose is fine)

**Lab.**
1. Draw your Compose stack as K8s objects on paper (use the cheat sheet above).
2. `kubectl api-resources` and `kubectl explain pod.spec.containers` : browse the API.
3. `kubectl get pods -n kube-system` : identify which are control plane vs add-ons.

**Done when.** [ ] You can explain "desired state vs actual state" in two sentences. [ ] You can name the 4 control plane components.

---

## Chapter 2: Your local cluster and kubectl fluency

**Needs:** Chapter 1, the Setup section.

**Why.** `kubectl` is your only hand. Speed here pays off in every chapter.

**Compose → K8s.** `docker ps` → `kubectl get pods`. `docker logs` → `kubectl logs`. `docker exec -it` → `kubectl exec -it`. `docker compose up` → `kubectl apply -f`.

**Learn.**
- kubeconfig, contexts, namespaces: `kubectl config`, `kubens`
- The verbs: `get`, `describe`, `logs`, `exec`, `apply`, `delete`, `port-forward`, `explain`, `diff`
- Output: `-o wide`, `-o yaml`, `-o jsonpath=...`, `--watch`
- `kubectl run` / `create` / `expose` (quick) vs `apply -f` (the real way)
- `--dry-run=client -o yaml` : generate YAML instead of writing it by hand
- Aliases (`k`), shell completion
- How Rancher Desktop builds images so the cluster sees them (dockerd mode)

**Lab.**
1. `kubectl create namespace nutshell`, then set it as the default for your context.
2. `kubectl run hello --image=nginx --dry-run=client -o yaml > hello.yaml`; read it, apply it, `port-forward` to it, delete it.
3. Build the API image: `docker build -t nutshell-api:0.1 fast_api` and confirm the cluster can run it with `kubectl run`+`--image-pull-policy=Never`.

**Done when.** [ ] You never need to Google the verb for "see logs", "shell in", "show YAML". [ ] `nutshell` is your default namespace.

---

## Chapter 3: Pods

**Needs:** Chapter 2.

**Why.** A Pod is the smallest deployable unit: one or more containers sharing network and storage. Everything else wraps Pods.

**Compose → K8s.** A Compose service is roughly one container; a Pod can hold several that share `localhost`.

**Learn.**
- Pod spec: `containers`, `image`, `command`/`args` (≈ Docker `ENTRYPOINT`/`CMD`), `env`, `ports`
- One IP per Pod, containers share `localhost`
- Pods are **ephemeral**: no one restarts a bare Pod on another node
- `restartPolicy`, phases, container states (Waiting, Running, Terminated)
- Multi-container patterns: **sidecar**, **init container**, ambassador
- Reading `kubectl describe pod` events (the #1 debug tool)
- Common errors: `ImagePullBackOff`, `CrashLoopBackOff`, `Pending`, `OOMKilled`

**Lab.**
1. Write `pod-api.yaml` for the `nutshell-api:0.1` image. Expect it to crash (no Postgres). Read the events and logs, explain *why*.
2. Add an `initContainer` that waits for a host (`busybox` + `nc`), see Pod status go `Init:0/1`.
3. Make a sidecar that tails a log file shared via `emptyDir`.
4. Break it on purpose: wrong image tag, memory limit of `10Mi`. Identify each error.

**Done when.** [ ] You can diagnose Pending / CrashLoopBackOff / ImagePullBackOff from `describe` alone. [ ] You know why you rarely create bare Pods.

---

## Chapter 4: Deployments, ReplicaSets, rollouts

**Needs:** Chapter 3.

**Why.** A Deployment gives you replicas, self-healing and zero-downtime updates. This is how your `api` and `mcp-server` will actually run.

**Compose → K8s.** `api` service → Deployment. `docker compose up --scale api=3` → `replicas: 3`. `restart: unless-stopped` → built in.

**Learn.**
- Deployment → ReplicaSet → Pods ownership chain
- Labels and `selector.matchLabels` (must match the Pod template, a classic mistake)
- Rolling update: `maxSurge`, `maxUnavailable`; `Recreate` strategy
- `kubectl rollout status | history | undo`, `kubectl scale`, `kubectl set image`
- Why `latest` tags are a trap; pinning versions or digests
- `imagePullPolicy`

**Lab.**
1. Deployment `mcp-server` (`replicas: 2`). Delete a Pod, watch it come back.
2. Change the image tag to a broken one, watch the rollout stall, `rollout undo`.
3. Scale to 5 and back. Watch ReplicaSets with `kubectl get rs -w`.
4. Set `maxUnavailable: 0` and observe the difference.

**Done when.** [ ] You can explain the Deployment → ReplicaSet → Pod chain. [ ] You rolled back a bad release.

---

## Chapter 5: Services and DNS

**Needs:** Chapter 4.

**Why.** Pod IPs change on every restart. A Service gives a stable name and load-balances across matching Pods. It is what `postgres` as a hostname was in Compose.

**Compose → K8s.** Compose's built-in DNS (`postgres:5432`) → Service DNS (`postgres.nutshell.svc.cluster.local`, or just `postgres` within the namespace).

**Learn.**
- Service types: **ClusterIP** (default), **NodePort**, **LoadBalancer** (k3s `svclb`), **ExternalName**, headless (`clusterIP: None`)
- `selector` → **Endpoints/EndpointSlices**: a Service with no endpoints means a label mismatch
- `port` vs `targetPort` vs `nodePort`
- CoreDNS: `<svc>.<ns>.svc.cluster.local`, search domains, `nslookup` from a debug Pod
- `kubectl port-forward svc/api 8000:8000` for local testing
- kube-proxy basics (iptables/IPVS), session affinity

**Lab.**
1. Expose `mcp-server` with a ClusterIP Service; `curl` it from a throwaway `curlimages/curl` Pod.
2. Deliberately mislabel and find the empty Endpoints.
3. `nslookup` the service from a busybox Pod; reach it via the short name and FQDN.
4. Expose it as NodePort and reach it from Windows.

**Done when.** [ ] You can debug "service unreachable" in 3 steps (endpoints, labels, targetPort). [ ] Pods talk to each other by name only.

---

## Chapter 6: ConfigMaps and Secrets

**Needs:** Chapter 5.

**Why.** Your `.env` mixes plain config (`LLM_BASE_URL`) with secrets (DB password, API keys). Images must stay environment-agnostic, so config is injected.

**Compose → K8s.** `env_file: .env` → `envFrom: configMapRef / secretRef`. Mounted config files → ConfigMap volumes.

**Learn.**
- ConfigMap from literals, files, env-files; consumed as env vars or as mounted files
- Secrets: **base64 is encoding, not encryption.** Who can read them (RBAC), and etcd encryption at rest
- `envFrom` vs `env.valueFrom`; mounted updates propagate to volumes but **not** to env vars (need a rollout)
- Immutable ConfigMaps/Secrets
- Triggering rollouts on config change (checksum annotation, Reloader)
- Never commit real Secrets to git: Sealed Secrets, SOPS, External Secrets (preview of Chapter 22)

**Lab.**
1. Split `fast_api/.env.example` into a ConfigMap and a Secret (`kubectl create secret generic ... --from-env-file`).
2. Inject into the API Pod with `envFrom`; verify with `kubectl exec ... -- env`.
3. Change a value, observe that env does **not** update until `rollout restart`.
4. Decode a Secret with `kubectl get secret -o jsonpath` and realise how weak base64 is.

**Done when.** [ ] No password is in a Deployment YAML. [ ] You know which of your `.env` keys belong in which object.

---

# Part B: Intermediate

## Chapter 7: Storage: volumes, PV, PVC

**Needs:** Chapter 6.

**Why.** Container disks vanish with the Pod. Postgres, Redis (`appendonly`), Ollama models and `uploaded_documents/` need durable storage.

**Compose → K8s.** `volumes: postgres_data:` → PVC. Bind mounts have no direct equivalent.

**Learn.**
- Volume types: `emptyDir`, `hostPath`, `configMap`, `secret`, `persistentVolumeClaim`
- PV (the disk), PVC (the request), **StorageClass** (the provisioner, k3s ships `local-path`)
- Access modes (`RWO`, `RWX`, `ROX`), reclaim policy (`Delete` vs `Retain`)
- Why `RWO` limits the API to one node when it writes uploads (hint: object storage later)
- `volumeMounts`, `subPath`, permissions/`fsGroup`
- Backup concepts and VolumeSnapshots

**Lab.**
1. Create a PVC; mount into a busybox Pod, write a file, delete the Pod, recreate it, file still there.
2. Find where `local-path` really stores data (inside the Rancher Desktop VM).
3. Create a PVC for `uploaded_documents/` and mount it in the API Pod.
4. Delete the PVC and observe `Delete` reclaim in action. Note why that is dangerous.

**Done when.** [ ] Data survives Pod deletion. [ ] You understand why Deleting a PVC deletes data.

---

## Chapter 8: Jobs and CronJobs

**Needs:** Chapter 4.

**Why.** One-shot tasks and schedules: DB migrations, the `ollama-pull` model download, nightly cleanups, eval runs (`fast_api/evals/run_evals.py`).

**Compose → K8s.** `ollama-pull` (`restart: "no"`) → Job. Cron on a host → CronJob.

**Learn.**
- Job: `completions`, `parallelism`, `backoffLimit`, `ttlSecondsAfterFinished`, `restartPolicy: Never/OnFailure`
- CronJob: schedule syntax, `concurrencyPolicy`, `startingDeadlineSeconds`, history limits
- Jobs as Helm hooks / pre-deploy migration step (Alembic)
- Idempotency: Jobs retry, so design for it

**Lab.**
1. A Job that runs `python -m evals.run_evals` against the API Service.
2. A Job that does `alembic upgrade head` before the API starts.
3. A CronJob every minute (for the lab) that prints the date; study history and cleanup.
4. Make a Job fail, watch `backoffLimit`.

**Done when.** [ ] You run a migration as a Job. [ ] You know why Jobs must be idempotent.

---

## Chapter 9: Ingress

**Needs:** Chapter 5.

**Why.** `port-forward` and NodePort are for debugging. Ingress gives host/path routing and TLS on one entry point. One front door: `api.localhost` → api, `/mcp` → mcp-server.

**Compose → K8s.** Compose's published ports → Ingress + Ingress Controller (Traefik on k3s).

**Learn.**
- Ingress (the rules) vs Ingress Controller (the software doing the work)
- `ingressClassName`, host and path rules, `pathType`
- TLS with a Secret; self-signed locally, cert-manager + Let's Encrypt in real life
- Gateway API: the successor to Ingress (concepts)
- Streaming: SSE / long-lived connections need timeouts adjusted (relevant to `/ask` streaming)

**Lab.**
1. Ingress for `api.localhost` → api Service. Hit it from the browser (`/docs`).
2. Path-based route for the MCP server.
3. Add local TLS with a self-signed cert.
4. Inspect the Traefik dashboard to see your routes.

**Done when.** [ ] `http://api.localhost/docs` works with no port-forward. [ ] You can say what an Ingress Controller adds.

---

## Chapter 10: StatefulSets: running Postgres and Redis

**Needs:** Chapters 7, 5.

**Why.** Databases need a stable identity and their own disk per replica, which Deployments do not give. This is also where you learn that **running databases in Kubernetes is hard**.

**Compose → K8s.** `postgres` and `redis` services → StatefulSet + headless Service + `volumeClaimTemplates`.

**Learn.**
- StatefulSet guarantees: stable names (`postgres-0`), ordered start/stop, per-Pod PVC
- Headless Service and per-Pod DNS (`postgres-0.postgres`)
- `volumeClaimTemplates`, `updateStrategy`, `podManagementPolicy`
- Why a single replica Postgres is fine for learning, and what HA needs (operators: CloudNativePG, Zalando, Crunchy)
- Redis: standalone vs Sentinel vs Cluster; `appendonly` persistence
- The honest alternative: managed Postgres/Redis outside the cluster

**Lab.**
1. StatefulSet `postgres` using `pgvector/pgvector:pg16` with a PVC and the Secret from Ch.6; add `pg_isready` probe.
2. Same for `redis:7-alpine` with `--appendonly yes`.
3. `kubectl exec` into postgres, create a table, delete the Pod, confirm data survived.
4. Connect from a temporary psql Pod using the Service name.

**Done when.** [ ] Data survives `delete pod postgres-0`. [ ] You can explain when *not* to run a DB in-cluster.

---

## Chapter 11: Deploy the whole python_nutshell stack

**Needs:** Chapters 1 to 10.

**Why.** This is the first milestone: the full app on K8s, replacing Compose.

**Compose → K8s.** The whole `docker-compose.yml` → `k8s/` directory.

**Learn.**
- Folder layout: `k8s/base/` with `namespace.yaml`, `configmap.yaml`, `secret.yaml` (placeholder), `postgres.yaml`, `redis.yaml`, `mcp-server.yaml`, `api.yaml`, `ingress.yaml`, `jobs/`
- Ordering without `depends_on`: probes + init containers + app retry logic
- Image loading with dockerd mode; no bind-mount dev loop (and why `--reload` is wrong in prod)
- **Ollama on the host**: reach host Ollama from the cluster (`host.docker.internal` / Rancher Desktop host alias) vs run it in-cluster (big PVC, CPU/RAM limits, optional)
- Correct Dockerfile for K8s: no `--reload`, non-root user, pinned versions

**Lab.**
1. Write manifests for all 5 pieces; apply with `kubectl apply -f k8s/base/`.
2. Run the migration Job, then bring up the API.
3. Reach `http://api.localhost/health/ready`, then exercise `/ask` end to end.
4. `kubectl delete ns nutshell`, re-apply: the whole stack comes back from files alone.

**Done when.** [ ] The app works end to end on Kubernetes. [ ] Everything is reproducible from `k8s/`.

---

## Chapter 12: Health probes and the pod lifecycle

**Needs:** Chapter 11.

**Why.** Without probes, K8s sends traffic to Pods that are not ready and never restarts hung ones. Your Compose healthcheck hits `/health/ready`; K8s splits that into three jobs.

**Compose → K8s.** `healthcheck:` → `startupProbe` + `readinessProbe` + `livenessProbe`.

**Learn.**
- **Readiness** (take out of Service?), **liveness** (restart?), **startup** (slow boot protection)
- Probe types: `httpGet`, `tcpSocket`, `exec`, `grpc`; `initialDelaySeconds`, `periodSeconds`, `failureThreshold`
- Anti-pattern: a liveness probe that checks the database (a DB blip restarts your whole API fleet)
- Graceful shutdown: SIGTERM, `terminationGracePeriodSeconds`, `preStop`, draining connections (uvicorn)
- PodDisruptionBudget (voluntary disruptions)

**Lab.**
1. Add the three probes to the API; separate `/health/live` (cheap) from `/health/ready` (checks DB/Redis).
2. Stop Postgres: API goes NotReady, is removed from endpoints, **not** restarted.
3. Make the app hang; watch liveness restart it.
4. Roll out an update while load-testing (`hey`/`k6`), confirm zero failed requests.

**Done when.** [ ] Rollouts cause no dropped requests. [ ] Liveness and readiness check different things.

---

## Chapter 13: Resources, QoS, scheduling

**Needs:** Chapter 11.

**Why.** An Ollama or embedding spike can starve Postgres. Requests and limits are how K8s shares a node, and `OOMKilled` is the price of getting them wrong.

**Learn.**
- `requests` (scheduling) vs `limits` (enforcement); CPU throttling vs memory OOM kill
- QoS classes: Guaranteed, Burstable, BestEffort
- `LimitRange`, `ResourceQuota` per namespace
- Scheduling: `nodeSelector`, node/pod **affinity** and **anti-affinity**, **taints and tolerations**, `topologySpreadConstraints`
- Priority classes and preemption
- Measuring first: `kubectl top` (metrics-server), sensible starting numbers for a FastAPI app and Postgres

**Lab.**
1. Set requests/limits on every workload; check `kubectl describe node` allocations.
2. Limit the API to 128Mi, trigger an OOM with a big upload, read `lastState`.
3. Create a Pod requesting more than the node has: see `Pending` and the scheduler's message.
4. Add a `ResourceQuota` to `nutshell`.

**Done when.** [ ] Every container has requests and limits. [ ] You can read a Pending event and say why.

---

## Chapter 14: Kustomize and manifest hygiene

**Needs:** Chapter 11.

**Why.** Copy-pasting YAML for dev / staging / prod does not scale. Kustomize is built into `kubectl` and needs no templates.

**Learn.**
- `base/` + `overlays/dev|prod/` structure, `kustomization.yaml`
- `patches` (strategic merge and JSON6902), `images:` tag override, `configMapGenerator`/`secretGenerator` with hash suffixes (automatic rollout on config change)
- `namePrefix`, `commonLabels`, namespaces
- `kubectl apply -k`, `kubectl kustomize` to preview
- Validation: `kubeconform`, `kubectl diff`, `kubectl apply --dry-run=server`
- Recommended labels (`app.kubernetes.io/*`)

**Lab.**
1. Convert `k8s/base` into base + `overlays/dev` (1 replica, small limits) and `overlays/prod` (3 replicas).
2. Use `configMapGenerator`, change a value, see the new hash trigger a rollout.
3. Validate with `kubeconform` in a script.

**Done when.** [ ] One command deploys dev, one deploys prod. [ ] `kubectl diff -k` is part of your habit.

---

## Chapter 15: Helm

**Needs:** Chapters 14, 11.

**Why.** Helm is the package manager of Kubernetes: most third-party software (Prometheus, Postgres operators, ingress, Argo CD) ships as charts, and you can package your own app.

**Learn.**
- Chart structure: `Chart.yaml`, `values.yaml`, `templates/`, `_helpers.tpl`, `NOTES.txt`
- Go templating: `{{ .Values.x }}`, `include`, `default`, `required`, `toYaml | nindent`, `range`, `if`
- `helm install | upgrade --install | rollback | uninstall | template | lint | diff`
- Release history stored as Secrets in the cluster
- Values layering: `-f values-dev.yaml --set`
- Subcharts, dependencies, hooks (`pre-upgrade` migration Job), tests
- Helm vs Kustomize: when each is better; using both (Argo CD)
- OCI registries for charts

**Lab.**
1. Install a public chart (`bitnami/redis` or `ingress-nginx`), study its values.
2. `helm create nutshell`, rewrite it for your stack; one chart, `values-dev.yaml` and `values-prod.yaml`.
3. Add a `pre-upgrade` hook running Alembic.
4. Break an upgrade on purpose and `helm rollback`.

**Done when.** [ ] `helm upgrade --install nutshell ./chart -f values-dev.yaml` deploys everything. [ ] You can roll back.

---

# Part C: Advanced

## Chapter 16: RBAC and ServiceAccounts

**Needs:** Chapter 11.

**Why.** Every Pod has an identity, and every kubectl user has permissions. Least privilege limits the blast radius, and it mirrors your own role-gating work in the app.

**Learn.**
- Authentication vs authorization; **Role / ClusterRole**, **RoleBinding / ClusterRoleBinding**
- ServiceAccounts, token projection, `automountServiceAccountToken: false` for apps that do not call the API
- `kubectl auth can-i`, `--as=system:serviceaccount:...`
- Namespaced vs cluster-wide scope
- Typical mistakes: binding `cluster-admin` to apps, wildcard verbs
- Audit logging concepts

**Lab.**
1. ServiceAccount for the API with no permissions and no mounted token.
2. A ServiceAccount + Role that lets a "reporter" Pod list Pods in `nutshell` only; prove it cannot read Secrets.
3. Create a read-only kubeconfig user for yourself.

**Done when.** [ ] `kubectl auth can-i` answers match your expectation. [ ] No app uses the default ServiceAccount.

---

## Chapter 17: NetworkPolicy and pod security

**Needs:** Chapters 5, 16. A CNI that enforces policies (k3s ships a policy controller; verify in the lab).

**Why.** By default every Pod can talk to every Pod. Postgres should accept traffic only from the API and MCP server.

**Learn.**
- NetworkPolicy: ingress/egress, `podSelector`, `namespaceSelector`, default-deny pattern; always allow DNS egress
- **Pod Security Standards** (privileged / baseline / restricted) and Pod Security Admission labels
- `securityContext`: `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, drop capabilities, `seccompProfile`
- Image hygiene: slim base images, scanning (`trivy`), pinned digests, no secrets in layers
- Secret management: Sealed Secrets, External Secrets, SOPS
- Admission policy: Kyverno / OPA Gatekeeper / ValidatingAdmissionPolicy

**Lab.**
1. Default-deny in `nutshell`, then add allow rules until the app works again.
2. Prove from a test Pod that it cannot reach Postgres, while the API can.
3. Harden the API Pod to the `restricted` standard (update the Dockerfile for a non-root user).
4. Scan the API image with `trivy image`.

**Done when.** [ ] Only API/MCP can reach Postgres. [ ] The API runs as non-root with a read-only filesystem.

---

## Chapter 18: Observability: logs, metrics, tracing

**Needs:** Chapters 11, 15 (Helm installs the stack). Pairs well with the AI course's observability chapters (Langfuse, OpenTelemetry).

**Why.** In a cluster Pods come and go, so `docker logs` is not enough. You need aggregated logs, metrics and traces.

**Learn.**
- `kubectl logs` (`-f`, `--previous`, `-c`, `-l`), `stern`, `k9s`
- Structured JSON logging from FastAPI so logs are queryable
- Metrics stack: **Prometheus** + **Grafana** (`kube-prometheus-stack` Helm chart), ServiceMonitor, `/metrics` endpoint (`prometheus-fastapi-instrumentator`)
- Key metrics: restarts, OOMKills, request latency/error rate, saturation (USE/RED)
- Logs stack: Loki + Promtail/Alloy
- Tracing: OpenTelemetry Collector, Tempo/Jaeger; link to LLM traces
- Alerts: Alertmanager basics; Kubernetes events

**Lab.**
1. Install `kube-prometheus-stack` with Helm; open Grafana via port-forward.
2. Expose `/metrics` from FastAPI, add a ServiceMonitor, build a latency panel.
3. Install Loki and query the API's logs by label.
4. Write one alert: API restart count > 3 in 10 minutes.

**Done when.** [ ] A dashboard shows API rate/latency/errors. [ ] You can find logs of a Pod that already died.

---

## Chapter 19: Autoscaling: HPA, VPA, KEDA

**Needs:** Chapters 12, 13, 18 (for custom metrics); metrics-server (bundled with k3s).

**Why.** Traffic and LLM calls are bursty. Scale `api` replicas automatically instead of guessing.

**Learn.**
- **HPA** on CPU/memory (`autoscaling/v2`), `behavior` (stabilization, scale-down policy)
- Custom/external metrics (requests/sec, queue depth) via Prometheus Adapter
- **KEDA**: scale on events (Redis list length, Postgres query, cron), scale to zero
- **VPA** (right-sizing recommendations); don't combine HPA+VPA on the same metric
- Cluster autoscaling concepts (cloud nodes), why locally you only have one node
- Why requests must be set for HPA percentage targets to work

**Lab.**
1. HPA on the API (min 1, max 5, 50% CPU). Generate load with `hey`/`k6`, watch scale-up and scale-down.
2. Tune `behavior` to scale down slowly.
3. Install KEDA, scale a worker on Redis list length (a future background-jobs design).

**Done when.** [ ] Load triggers scaling without manual action. [ ] You know why scale-down is deliberately slow.

---

## Chapter 20: Cluster internals and troubleshooting

**Needs:** Chapters 1 to 13.

**Why.** Real clusters fail in ways tutorials skip. This chapter builds the muscle to find the cause fast, and to understand what is under the hood.

**Learn.**
- The debugging ladder: `get` → `describe` → `logs` (`--previous`) → `events` → `exec` / `kubectl debug` (ephemeral containers) → node level
- Failure catalogue: Pending (resources/taints/PVC), ImagePullBackOff, CrashLoopBackOff, OOMKilled, Evicted, readiness stuck, Service with no endpoints, DNS failures, Terminating forever (finalizers)
- Internals: etcd, API server request flow, admission controllers, scheduler filtering/scoring, kubelet, CNI, CRI, kube-proxy
- Node maintenance: `cordon`, `drain`, `uncordon`, PDBs
- Multi-node practice with `kind`; upgrade strategy and version skew
- Backup/restore: etcd snapshots, Velero
- Troubleshooting tools: `netshoot`, `kubectl debug node/...`, `crictl`

**Lab.**
1. Create a `kind` cluster with 3 nodes; deploy the app, `drain` one node, watch rescheduling and PDB.
2. Run a "break it" game: from a scripted set of 8 faults (wrong selector, bad secret key, full PVC, NetworkPolicy block, ...), fix each using only kubectl.
3. Use `kubectl debug` with `netshoot` against a running API Pod.
4. Walk through what happens on `kubectl apply` of a Deployment, tracing each component.

**Done when.** [ ] You can fix each of the 8 faults without hints. [ ] You can narrate the life of a Pod from `apply` to `Running`.

---

## Chapter 21: CI/CD to Kubernetes

**Needs:** Chapters 14 or 15.

**Why.** Manual `kubectl apply` from a laptop does not survive a team. Automate: test → build image → push → deploy.

**Learn.**
- Pipeline stages: lint/test (`pytest`), build (`docker buildx`), scan (`trivy`), push (GHCR / Docker Hub / ACR), deploy
- Image tagging: git SHA, never `latest`; immutable tags and digests
- Deploying: push (`kubectl`/`helm` from CI with a scoped ServiceAccount) vs pull (GitOps, Ch.22)
- Environment promotion: dev → staging → prod, approvals
- Dev loop tools: Skaffold, Tilt, Telepresence (replace your Compose bind-mount workflow)
- Secrets in CI; short-lived credentials (OIDC) instead of long-lived kubeconfigs
- Smoke tests and automatic rollback

**Lab.**
1. GitHub Actions: on push, run tests, build and push `ghcr.io/<you>/nutshell-api:<sha>`.
2. Update the Kustomize `images:` tag (or Helm value) with the new SHA.
3. Set up Skaffold for the inner loop: edit code, auto rebuild and redeploy locally.

**Done when.** [ ] A push to a branch results in a new running version without manual steps. [ ] Images are tagged by SHA.

---

## Chapter 22: GitOps with Argo CD

**Needs:** Chapter 21, Chapter 15 or 14.

**Why.** Git becomes the single source of truth. The cluster *pulls* its desired state, so drift is detected and every change is reviewed and revertible.

**Learn.**
- GitOps principles; Argo CD vs Flux
- Install Argo CD; `Application`, `AppProject`, sync policies (auto-sync, prune, self-heal)
- App-of-apps and ApplicationSets for multi-env
- Rollback = `git revert`
- Secrets in GitOps: Sealed Secrets / External Secrets / SOPS
- Progressive delivery with **Argo Rollouts**: canary and blue/green with metric analysis
- Repo layout: app code repo vs config repo

**Lab.**
1. Install Argo CD; point an `Application` at `k8s/overlays/dev` in this repo.
2. Edit a manifest in git, watch sync. Change something with `kubectl edit`, watch `selfHeal` revert it.
3. Convert the API to an Argo Rollout with a 20% → 100% canary.
4. Add Sealed Secrets so credentials can live in git.

**Done when.** [ ] A merged PR is the only way to change the cluster. [ ] A canary release rolls back automatically on bad metrics.

---

# Part D: Amazon EKS

## Learning EKS without an AWS account

Be honest about the constraint: **EKS cannot be fully run locally.** The EKS control plane is a managed AWS service. There is no free emulator for it (LocalStack's EKS support is in its paid tier). So use a staged approach:

| Stage | Needs AWS account? | What you can do | Cost |
|---|---|---|---|
| **A. Offline** | No | Learn the concepts, read and write the real EKS manifests/configs, validate them (`eksctl ... --dry-run`, `terraform validate/plan` against mocks, `kubeconform`). Practise every Kubernetes part on Rancher Desktop or `kind` | Free |
| **B. Local stand-ins** | No | Simulate EKS pieces: `kind` multi-node (managed node groups), MetalLB (LoadBalancer), `ingress-nginx` (stand-in for ALB), MinIO (S3), LocalStack free tier (IAM, S3, SQS, STS concepts), Karpenter concepts on paper | Free |
| **C. Real EKS, short and capped** | **Yes** | Create a cluster for 2 to 3 hour sessions, run Chapters 24 to 28 labs, destroy it the same day | roughly $0.10/hr control plane + nodes + NAT; a few dollars per session |

Recommended: do **Stage A and B first** (Chapters 23 to 28 are written so every "Learn" and most "Lab" items work there), then **one or two capped Stage C sessions** to see the real thing.

**If you create an AWS account later** (verify current terms on aws.amazon.com/free, they have changed recently):
- New accounts get a free plan with promotional credits; EKS is **not** in the always-free tier, but credits usually cover a few lab sessions. A credit card is required.
- First, before any resource: enable **MFA on the root user**, create an **IAM Identity Center / IAM admin user** and stop using root, then create an **AWS Budget with email alerts at $5, $20** and a **zero-spend budget**.
- Prefer one region (e.g. `ap-south-1` Mumbai, or `us-east-1`) and always tag resources `project=nutshell-lab`.
- **Always tear down** the same day (`eksctl delete cluster` / `terraform destroy`), then check **NAT Gateways, Load Balancers, EBS volumes and Elastic IPs** in the console. Those are what silently bill you.

**Extra tools for this part** (install when Chapter 23/24 asks):

| Tool | Why | Install (PowerShell) |
|---|---|---|
| AWS CLI v2 | Talk to AWS, `aws eks update-kubeconfig` | `winget install Amazon.AWSCLI` |
| `eksctl` | The official EKS cluster CLI | `winget install eksctl` (or `choco install eksctl`) |
| Terraform (or OpenTofu) | Infrastructure as code, the real-world way to build EKS | `winget install Hashicorp.Terraform` |
| `kind` | Local multi-node stand-in | `winget install Kubernetes.kind` |
| LocalStack (free tier) | Local IAM/S3/STS practice | `pip install localstack awscli-local` |
| `kubectl` / `helm` | Already installed | n/a |

---

## Chapter 23: AWS foundations for EKS (no account needed)

**Needs:** Chapters 1 to 5.

**Why.** EKS is "Kubernetes plus AWS plumbing". Most EKS confusion is AWS confusion (IAM, VPC), not Kubernetes confusion.

**Compose → K8s.** Your laptop network → a **VPC**. Docker's default bridge → **subnets** and **security groups**. `docker login` → **IAM** and **ECR**.

**Learn.**
- **IAM**: users, roles, policies (JSON), trust policies, `sts:AssumeRole`, least privilege, why roots and access keys are dangerous, IAM Identity Center
- **VPC**: CIDR, public vs private subnets, route tables, Internet Gateway, **NAT Gateway** (the surprise cost), Availability Zones, security groups vs NACLs
- **EC2** basics (instance types, AMIs, On-Demand vs Spot), **EBS**, **S3**, **ECR** (image registry), **CloudWatch**
- How EKS is split: AWS-run **control plane** (in AWS's account) vs your **data plane** (nodes in your VPC)
- Compute choices: **managed node groups**, **self-managed nodes**, **Fargate**, **EKS Auto Mode**, Karpenter
- Pricing model: control plane per hour + nodes + NAT + load balancers + data transfer
- Read-only AWS: the free AWS docs, the EKS Best Practices Guide (aws.github.io/aws-eks-best-practices), and the `eksctl` / `terraform-aws-modules/eks` repos

**Lab (offline).**
1. Draw the VPC for an EKS cluster: 3 AZs, public + private subnets, NAT, ALB in public, nodes in private. Label what costs money.
2. Write (don't apply) an IAM trust policy for a role that a Kubernetes ServiceAccount could assume.
3. With LocalStack free tier: create a bucket, a role and a policy, and call `sts assume-role` to feel the flow.
4. Push-style practice: tag your local image the ECR way (`<acct>.dkr.ecr.<region>.amazonaws.com/nutshell-api:0.1`) and note what `aws ecr get-login-password` would do.

**Done when.** [ ] You can explain public vs private subnet and why NAT exists. [ ] You can explain what a trust policy is. [ ] You can name the 4 biggest EKS cost items.

---

## Chapter 24: EKS clusters: eksctl and Terraform

**Needs:** Chapter 23, Chapter 15 (Helm).

**Why.** Creating a cluster by hand in the console does not scale. Real teams use `eksctl` (quick) or Terraform (standard).

**Learn.**
- `eksctl` **ClusterConfig** YAML: `metadata`, `vpc`, `managedNodeGroups`, `addons`, `iam.withOIDC`
- Terraform module `terraform-aws-modules/eks/aws` + `vpc/aws`: inputs, outputs, state (remote state in S3 + locking)
- Cluster access: `aws eks update-kubeconfig`, **access entries** (modern) vs the legacy `aws-auth` ConfigMap, endpoint access (public/private)
- Add-ons: CoreDNS, kube-proxy, VPC CNI, EBS CSI, Pod Identity Agent
- Version policy and cost of extended support
- EKS Auto Mode vs managed node groups: what AWS manages for you

**Lab.**
1. (Stage A) Write `eks/cluster.yaml` for `eksctl`: 2 AZs, one managed node group `t3.medium` x2, OIDC on. Run `eksctl create cluster -f eks/cluster.yaml --dry-run` and read the generated config.
2. (Stage A) Write `eks/terraform/main.tf` using the community VPC + EKS modules. `terraform init && terraform validate`. Read the plan structure.
3. (Stage B) Make a 3-node `kind` cluster and treat it as "managed node group"; label nodes like `eks.amazonaws.com/nodegroup`.
4. (Stage C, optional, capped) Apply for real, `update-kubeconfig`, `kubectl get nodes`, then **destroy the same day**.

**Done when.** [ ] You can explain what `eksctl create cluster` creates in AWS. [ ] You have a validated Terraform config. [ ] You know the destroy checklist.

---

## Chapter 25: EKS networking: VPC CNI, load balancers, ingress

**Needs:** Chapters 5, 9, 24.

**Why.** EKS networking differs from your local Traefik setup: Pods get **real VPC IPs**, and Services/Ingresses create **AWS load balancers**.

**Learn.**
- **Amazon VPC CNI**: Pod IPs from the subnet, ENIs and IPs-per-node limits, prefix delegation, why you can run out of IPs
- Service `type: LoadBalancer` → NLB; Ingress → **ALB** via the **AWS Load Balancer Controller** (Helm), annotations, target type `ip` vs `instance`
- ACM certificates for TLS, Route 53 + **ExternalDNS**
- Security groups for Pods, NetworkPolicy on EKS (VPC CNI network policy support or Calico/Cilium)
- Private clusters, VPC endpoints (ECR, S3, STS) to avoid NAT costs
- Stage-B stand-ins: MetalLB for LoadBalancer, `ingress-nginx` for Ingress; compare the YAML

**Lab.**
1. Write the Ingress for `api` with ALB annotations (`alb.ingress.kubernetes.io/scheme`, `target-type: ip`, `healthcheck-path: /health/ready`). Validate with `kubeconform`.
2. (Stage B) Run the same app on `kind` with MetalLB + `ingress-nginx`; note exactly which YAML lines change vs Chapter 9.
3. Compute the maximum Pods per node for `t3.medium` from ENI limits.
4. (Stage C) Install the Load Balancer Controller, expose the API, curl the ALB DNS name, delete it.

**Done when.** [ ] You can explain why Pods consume VPC IPs. [ ] You can convert Traefik Ingress YAML into ALB Ingress YAML.

---

## Chapter 26: EKS identity and storage: IRSA / Pod Identity, EBS, EFS

**Needs:** Chapters 7, 16, 23, 24.

**Why.** Pods must call AWS (S3, Bedrock, Secrets Manager) **without access keys**. And your PVCs now become EBS volumes.

**Learn.**
- **IRSA** (IAM Roles for Service Accounts): OIDC provider, trust policy, ServiceAccount annotation `eks.amazonaws.com/role-arn`
- **EKS Pod Identity**: the newer, simpler mechanism; when to use which
- Never put `AWS_ACCESS_KEY_ID` in a Secret; how the SDK's credential chain finds the web identity token
- **EBS CSI driver**: `gp3` StorageClass, AZ-bound volumes (a Pod can't move across AZs with its disk), snapshots
- **EFS** for `RWX` shared storage; **S3** as the real answer for `uploaded_documents/`
- **Secrets Manager / Parameter Store** with External Secrets Operator or the Secrets Store CSI driver
- Stage B: MinIO as S3, plain Secrets as the stand-in

**Lab.**
1. Write a ServiceAccount + IAM role JSON (trust + S3 read policy) for the API; keep it in `eks/iam/`.
2. Write a `gp3` StorageClass and a StatefulSet PVC for Postgres; explain the AZ-binding problem.
3. (Stage B) Run MinIO; change the API's upload code path to use an S3-compatible endpoint (boto3 `endpoint_url`) so the same code works on AWS.
4. (Stage C) Prove with `aws sts get-caller-identity` inside a Pod that it assumed the role with no keys.

**Done when.** [ ] You can explain IRSA end to end. [ ] No AWS keys appear in any manifest. [ ] You know why Postgres on EBS is zone-pinned.

---

## Chapter 27: EKS operations: nodes, Karpenter, upgrades, observability

**Needs:** Chapters 13, 18, 19, 20, 24.

**Why.** Running EKS is mostly day-2 work: sizing nodes, scaling nodes, upgrading versions, seeing what is wrong.

**Learn.**
- Node groups: instance types, AMI types (AL2023, Bottlerocket), Spot, taints, GPU node groups for Ollama (`g5`/`g6`, NVIDIA device plugin)
- **Cluster Autoscaler** vs **Karpenter** (`NodePool`, `EC2NodeClass`, consolidation), Fargate trade-offs
- **Upgrades**: control plane first, then add-ons, then nodes; skew rules; PDBs; blue/green node groups; the deprecation-API check (`pluto`, `kubent`)
- **Observability**: CloudWatch Container Insights vs your Prometheus/Grafana stack from Chapter 18, control plane logs, **Amazon Managed Prometheus/Grafana**
- Security: private endpoint, GuardDuty EKS, Pod Security, image scanning in ECR, KMS envelope encryption of Secrets
- Backup/DR: Velero, multi-AZ design, RPO/RTO

**Lab.**
1. Write a Karpenter `NodePool` + `EC2NodeClass` for Spot `t3`/`m5` and review the consolidation settings (Stage A, paper).
2. Write the upgrade runbook for 1.N → 1.N+1 as a checklist file `eks/UPGRADE.md`.
3. (Stage B) On `kind`, `cordon`/`drain` a node and watch Pods reschedule, simulating a node-group roll.
4. Run `kubent` against your manifests for removed APIs.

**Done when.** [ ] You can explain Karpenter vs Cluster Autoscaler. [ ] You have a written, ordered upgrade plan.

---

## Chapter 28: Run python_nutshell on EKS, and cost control

**Needs:** Chapters 11, 14 or 15, 21, 22, 23 to 27.

**Why.** The capstone: take your working local stack and make it EKS-ready, then (optionally) run it for real for a few hours.

**Learn.**
- What changes from local to EKS: image from **ECR** (not local build), `gp3` storage, ALB Ingress, IRSA, managed data stores
- **Production choice**: RDS PostgreSQL (with pgvector) and ElastiCache for Redis instead of in-cluster StatefulSets
- Ollama on EKS: GPU nodes are expensive; alternatives are Amazon Bedrock or a hosted endpoint, and the config switch (`LLM_BASE_URL`)
- Kustomize `overlays/eks` or Helm `values-eks.yaml`
- CI/CD: GitHub Actions OIDC → AWS role → `docker push` to ECR → Argo CD syncs
- **FinOps**: tags, Budgets, right-sizing, Spot, schedule-down, cleanup scripts; **teardown checklist**

**Lab.**
1. Create `k8s/overlays/eks` (or `values-eks.yaml`) changing: image registry, StorageClass, Ingress class, ServiceAccount annotation, external DB host.
2. Write a GitHub Actions workflow (not run) that logs into AWS via OIDC and pushes to ECR.
3. Write `eks/teardown-checklist.md`: ordered delete steps and the console places to verify nothing bills.
4. (Stage C, capped) Deploy for a 2 to 3 hour session, run `/ask` end to end through the ALB, then run the checklist and confirm in Cost Explorer.

**Done when.** [ ] One overlay turns your local stack into an EKS stack. [ ] You have a teardown checklist and used it. [ ] You can estimate the monthly cost of the stack and name 3 ways to cut it.

---

# Part E: Expert (optional depth)

## Chapter 29: Operators, CRDs, extending Kubernetes

**Needs:** Chapters 10, 20 (and 15, since operators install via Helm).

**Why.** Operators encode human operational knowledge (backups, failover, upgrades) in a controller. They are how serious stateful software runs on K8s, and how Kubernetes stays extensible.

**Learn.**
- **CustomResourceDefinition** (a new object type) + **controller** (reconcile loop) = operator
- Using operators: **CloudNativePG** for Postgres (HA, backups, PITR), cert-manager, KEDA, Argo CD are all operators
- Writing one: Kubebuilder / Operator SDK (Go), or Kopf (**Python**, fits this repo)
- Admission webhooks (mutating/validating), finalizers, owner references
- API aggregation, controller-runtime concepts

**Lab.**
1. Replace the hand-made Postgres StatefulSet with a CloudNativePG `Cluster` (2 instances); kill the primary, watch failover.
2. Take a backup and restore to a new cluster.
3. Write a tiny Kopf operator for a `Document` CRD that creates a Job when a resource is added.

**Done when.** [ ] You can explain CRD vs operator. [ ] Postgres failover happens without data loss in your lab.

---

## Chapter 30: Service mesh, GPUs for Ollama, cloud, certification

**Needs:** Chapters 1 to 28.

**Why.** The long tail: what you will meet at work or when you take the app to a real cloud.

**Learn.**
- **Service mesh** (Istio, Linkerd, Cilium): mTLS between services, traffic shifting, retries; costs vs benefits. Usually not needed for a handful of services
- **GPU workloads**: NVIDIA device plugin / GPU Operator, `nvidia.com/gpu` resource requests, node pools and taints for Ollama or vLLM, model storage caching, KServe for model serving
- **Managed Kubernetes**: EKS / GKE / AKS differences, cloud LoadBalancers, managed disks, IAM-to-ServiceAccount (IRSA / Workload Identity), cluster autoscaler / Karpenter
- Multi-tenancy, multi-cluster, cost control (requests right-sizing, spot nodes, Kubecost)
- Platform engineering basics, Backstage
- **Certification path**: **CKAD** (developer, best fit now), **CKA** (admin), **CKS** (security). Practise with killer.sh and speed with `kubectl` imperative commands

**Lab.**
1. Mesh: install Linkerd in `kind`, observe automatic mTLS between api and postgres.
2. Paper design: how Ollama would run on a GPU node pool in a cloud (taints, requests, PVC for models, HPA on queue depth).
3. Deploy the stack to a free-tier managed cluster (GKE Autopilot / AKS / EKS) with Helm and Argo CD, tear down after.
4. Take a CKAD mock exam; list weak areas and map them back to chapters.

**Done when.** [ ] You can decide whether this project needs a mesh. [ ] You have a concrete plan for running Ollama on GPUs.

---

## Appendix A: kubectl quick reference

```bash
# context and namespace
kubectl config get-contexts
kubectl config set-context --current --namespace=nutshell

# inspect
kubectl get pods,svc,deploy,pvc,ingress -o wide
kubectl describe pod <pod>
kubectl get events --sort-by=.lastTimestamp
kubectl get pod <pod> -o yaml
kubectl explain deployment.spec.strategy

# logs and shell
kubectl logs -f deploy/api
kubectl logs <pod> --previous
kubectl exec -it deploy/api -- sh
kubectl debug -it <pod> --image=nicolaka/netshoot --target=api

# apply and change
kubectl apply -f k8s/base/            # or -k k8s/overlays/dev
kubectl diff -f k8s/base/
kubectl rollout status deploy/api
kubectl rollout undo deploy/api
kubectl rollout restart deploy/api
kubectl scale deploy/api --replicas=3
kubectl set image deploy/api api=nutshell-api:0.2

# access and test
kubectl port-forward svc/api 8000:8000
kubectl run tmp --rm -it --image=busybox -- sh
kubectl auth can-i get secrets --as=system:serviceaccount:nutshell:api

# generate YAML instead of writing it
kubectl create deployment api --image=nutshell-api:0.1 --dry-run=client -o yaml
```

## Appendix B: Common errors

| Symptom | Usual cause | First command |
|---|---|---|
| `ImagePullBackOff` | Wrong tag, private registry, or image not visible to cluster (containerd vs dockerd) | `describe pod` |
| `CrashLoopBackOff` | App exits (bad env, DB unreachable) | `logs --previous` |
| `Pending` | Not enough CPU/memory, unbound PVC, taint | `describe pod` (Events) |
| `OOMKilled` | Memory limit too low | `describe pod` (Last State) |
| Service returns nothing | Label/selector mismatch, wrong `targetPort`, no ready Pods | `get endpoints <svc>` |
| Config change not applied | Env vars are read at start | `rollout restart` |
| Ingress 404 | Wrong host/path or `ingressClassName` | `describe ingress` |
| Stuck `Terminating` | Finalizer or hung process | `get pod -o yaml` (finalizers) |
