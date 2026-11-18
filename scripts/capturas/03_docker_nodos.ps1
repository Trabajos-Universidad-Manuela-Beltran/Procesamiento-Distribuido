Set-Location G:\
Comentario 'Se levantan los seis nodos, cada uno con 1 CPU y 512 MB'
Ejecutar 'docker compose up -d'
Start-Sleep -Seconds 25
Ejecutar 'docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"'
Comentario 'Límites y seguridad de un nodo'
Ejecutar 'docker inspect procdist-nodo1-1 --format "CPU={{.HostConfig.NanoCpus}} memoria={{.HostConfig.Memory}} procesos={{.HostConfig.PidsLimit}} soloLectura={{.HostConfig.ReadonlyRootfs}} usuario={{.Config.User}}"'
