sum by (pod)(
  container_memory_rss{
    pod="app1-b5cf4c485-v88lh",
    container!="POD"
  }
)/1024/1024
gives 830mb

sum by (pod)(
  container_memory_working_set_bytes{
    pod="app1-b5cf4c485-v88lh",
    container!="POD"
  }
)/1024/1024
gives 850mb

sum by (pod)(
  container_memory_cache{
    pod="app1-b5cf4c485-v88lh",
    container!="POD"
  }
)/1024/1024
gives 26mb


avg_over_time(
 (
  sum by (pod)(
   container_memory_working_set_bytes{
    pod="app1-b5cf4c485-v88lh",
    container!="POD"
   }
  )
 )[10m:]
)
/1024/1024
gives 860 mb

kubectl top pods gives 410mb

echo $(( $(cat /sys/fs/cgroup/memory.current) / 1024 / 1024 ))
gives 415 mb

During load prometheus and kubectl top pods gives proper memory, i think or there could be any issue in above prometheus queries
