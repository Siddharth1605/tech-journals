prometheus query : optimized 
	app1 pod contains 3 containers
		container="app1" actual application container 
		container="POD" created dynamically to store pod's network, and metadata
		container="" created by metrics component to fetch metrics 

will provide additional memory
container_memory_working_set_bytes{
  pod="app1-85d4b4dd56-bmclb",
  container!="POD"
}	

will provide exact memory used by our application
container_memory_working_set_bytes{
  pod="app1-85d4b4dd56-bmclb",
  container=~".+",
  container!="POD"
}
