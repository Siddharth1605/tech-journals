
[2026/08/10 10:27:05.083] [ warn] [engine] failed to flush chunk '1-1786357624.908943448.flb', retry in 10 seconds: task_id=80, input=tail.0 > output=es.0 (out_id=0)
[2026/08/10 10:27:06.080] [ warn] [engine] failed to flush chunk '1-1786357603.15237837.flb', retry in 40 seconds: task_id=66, input=tail.0 > output=es.0 (out_id=0)
[2026/08/10 10:27:06.080] [ warn] [engine] failed to flush chunk '1-1786357545.5606282.flb', retry in 108 seconds: task_id=30, input=tail.0 > output=es.0 (out_id=0)
[retfusion@-k8s-master config3]$ kubectl logs -n logging -l app.kubernetes.io/name=fluent-bit --tail=200 | grep -Ei "error/warn/retry/flush/es/http"
[retfusion@-k8s-master config3]$ kubectl get pods -n logging -o wide
NAME                          READY   STATUS    RESTARTS   AGE     IP                NODE                 NOMINATED NODE   READINESS GATES
fluent-bit-vtl9h              1/1     Running   0          9m50s   x.y.z.151   k8s-master   <none>           <none>
logging-es-default-0          1/1     Running   0          30m     x.y.z.158   k8s-master   <none>           <none>
logging-kb-6f787bcfbd-wbch4   1/1     Running   0          23m     x.y.z.144   k8s-master   <none>           <none>
[retfusion@-k8s-master config3]$ kubectl logs -n logging logging-es-default-0 --tail=200
Defaulted container "elasticsearch" out of: elasticsearch, elastic-internal-init-filesystem (init), elastic-internal-suspend (init)
{"@timestamp":"2026-08-10T10:09:16.621Z","log.level": "INFO","message":"adding index template [.kibana-siem-dashboard-migrations-migrations] for index patterns [.kibana-siem-dashboard-migrations-migrations-*]", "ecs.version": "1.2.0","service.name":"ES_ECS","event.dataset":"elasticsearch.server","process.thread.name":"elasticsearch[logging-es-default-0][masterService#updateTask][T#3]","log.logger":"org.elasticsearch.cluster.metadata.MetadataIndexTemplateService","trace.id":"a2f2c985bcfde7ba9c060dbad9f4549c","elasticsearch.cluster.uuid":"OiK2uNyeRdu302oMTdHLoA","elasticsearch.node.id":"dOnTolmJTgK1Tr02tDFMjQ","elasticsearch.node.name":"logging-es-default-0","elasticsearch.cluster.name":"logging"}

i cant go inside fluentbit pod - no ssh option. I've tried efk stack from various sources to install - maybe lab setup is not proper 

If you cant find the sln, atleast tell the rca - because no gpts can able to find sln. - Maybe because of huge xml logs our applications writes but not sure - as we are not performing any operation only startup log is there 
