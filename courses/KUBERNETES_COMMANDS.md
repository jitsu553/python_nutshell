| Command | Description | Comment |
|---|---|---|
| `kubectl api-resources` | Lists every object type the cluster knows | Useful for browsing; run it once to see what exists |
| `kubectl explain <field>` | Shows built-in docs for a YAML field | Useful when writing YAML, replaces most web searches |
| `kubectl config current-context` | Shows which cluster you're talking to | Essential before any delete or scale |
| `kubectl config get-contexts` | Lists all clusters in your kubeconfig | Essential before any delete or scale |
| `kubectl get nodes` | Lists the machines in the cluster | Quick health check; `Ready` means fine |
| `kubectl get pods -A` | Lists Pods in all namespaces | Good for a broad look; noisy day to day, prefer a namespace |
| `kubectl get pods -n <namespace>` | Lists Pods in one namespace | Use this unless you set a default namespace |
| `kubectl create namespace <namespace>` | Creates a namespace | Fine for practice; in real projects keep it in a YAML file |
| `kubectl config set-context --current --namespace=<namespace>` | Sets your default namespace | Saves typing `-n` every time |
| `kubectl apply -f <file>` | Creates or updates objects from a file | The main way to deploy; prefer it over every imperative command below |
| `kubectl delete -f <file>` | Deletes what the file created | Best way to delete what you created from a file |
| `kubectl get <type>` | Lists objects of that type | Core command |
| `kubectl get <type> -o wide` | Same, with extra columns (node, IP) | Useful when checking where Pods run |
| `kubectl get <type> -o yaml` | Prints the full object as YAML | Useful to see what the cluster stored, including `status` |
| `kubectl get <type> -w` | Keeps running and prints each change | Great for watching rollouts; use it in a second terminal |
| `kubectl get pods -l <label>` | Lists Pods that carry that label | Better than typing Pod names; they change every time |
| `kubectl get deploy,rs,pods -l <label>` | Shows Deployments, ReplicaSets and Pods at once | Best single view of the ownership chain |
| `kubectl describe <type> <name>` | Detailed view; read the Events at the bottom | The first thing to run when something is wrong |
| `kubectl logs <pod>` | Shows a Pod's output | Core command; see the next row for a shortcut |
| `kubectl logs deploy/<deployment>` | Shows logs from one of the Deployment's Pods | Better than looking up a Pod name first |
| `kubectl logs <pod> -c <container>` | Shows one container's output | Needed only when a Pod has several containers |
| `kubectl logs <pod> --previous` | Shows the output of the previous (crashed) run | Essential for `CrashLoopBackOff` |
| `kubectl exec -it <pod> -- sh` | Opens a shell inside a Pod | For debugging only; don't fix things inside a Pod, change the YAML |
| `kubectl port-forward pod/<pod> <local-port>:<pod-port>` | Forwards a local port to the Pod | Fine for testing; use a Service or Ingress for real access (later chapters) |
| `kubectl run <pod> --image=<image> --dry-run=client -o yaml` | Prints generated YAML without creating anything | Handy starter template; save it to a file and edit it |
| `kubectl delete pod <pod>` | Deletes a Pod (a Deployment replaces it, a bare Pod stays gone) | Good for testing self-healing; to restart Pods use `rollout restart` instead |
| `kubectl delete deploy <deployment>` | Deletes a Deployment by name, along with its ReplicaSets and Pods | Right way to remove an app when you don't have the file |
| `kubectl delete deploy -l <label>` | Deletes every Deployment with that label | Broad; check with `get` first |
| `kubectl delete deploy --all` | Deletes every Deployment in the current namespace | Dangerous; check the context and namespace first |
| `kubectl delete deploy <deployment> --cascade=orphan` | Deletes only the Deployment and leaves its Pods running as bare Pods | Rarely needed; the leftover Pods are no longer replaced if they die |
| `kubectl delete rs <replicaset>` | Deletes a ReplicaSet and its Pods; a Deployment recreates it | Not needed and not beneficial: use `kubectl rollout restart deploy/<deployment>` instead. Deleting an old one also removes a rollback point |
| `kubectl scale deploy/<deployment> --replicas=<number>` | Changes how many Pods you want | Correct way to scale; better still, edit `replicas` in the YAML and apply |
| `kubectl scale rs/<replicaset> --replicas=<number>` | Changes the Pod count of a ReplicaSet | Not needed and not beneficial: a Deployment resets it within seconds. Scale the Deployment instead |
| `kubectl rollout status deploy/<deployment>` | Waits and reports whether the rollout finished or is stuck | Essential after every apply that changes the template |
| `kubectl rollout status deploy/<deployment> --timeout=<seconds>s` | Same, but gives up after that time | Useful in scripts and CI so they don't hang |
| `kubectl rollout history deploy/<deployment>` | Lists past revisions | Run before `undo` to see what you can go back to |
| `kubectl rollout undo deploy/<deployment>` | Goes back to the previous revision | Quick fix for a bad release; then fix the YAML so the file matches |
| `kubectl rollout restart deploy/<deployment>` | Replaces every Pod one by one without changing the YAML | The right way to restart Pods; better than deleting Pods or ReplicaSets |
| `kubectl set image deploy/<deployment> <container>=<image>` | Changes the image from the command line (the file is not updated) | Not recommended: the YAML and cluster drift apart. Edit `image:` in the file and `apply` |
| `kubectl diff -f <file>` | Shows what `apply` would change | Useful before `apply` and for spotting drift |
| `docker build -t <image> <folder>` | Builds an image the local cluster can use | Core command; use a new tag for each version |
| `docker tag <image> <new-image>` | Adds a second tag to an image | Only for practising updates; real versions come from real builds |
| `kubectl get svc` | Lists Services with type, CLUSTER-IP and ports | Core command; `EXTERNAL-IP <pending>` means no load balancer controller |
| `kubectl get svc <service>` | Shows one Service | Quick check that the type and ports are what you wrote |
| `kubectl get endpoints <service>` | Lists the Pod IPs and ports a Service sends traffic to | First check when a Service fails: `<none>` means the selector matches no Pods. Deprecated in favour of EndpointSlices but still handy |
| `kubectl get endpointslices` | Same information in the newer object | What Kubernetes uses internally; use it once `Endpoints` is removed |
| `kubectl describe svc <service>` | Shows the Service's selector, targetPort and endpoints | Compare its `Selector` and `TargetPort` with the Pods and the app's real port |
| `kubectl get pods -l <label> -o wide` | Lists matching Pods with their IPs | The IPs should match the Service's endpoints |
| `kubectl port-forward svc/<service> <local-port>:<service-port>` | Forwards a local port to a Service | Everyday way to reach a ClusterIP Service from Windows; the left number is the local port you choose |
| `kubectl delete svc <service>` | Deletes a Service | Safe: the Pods keep running; recreate it from the file with `apply` |
