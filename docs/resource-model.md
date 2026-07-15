# Modelo de recursos

Dimensionado sobre el hardware real: **Intel i5-4460 (4 núcleos), 15 GiB de RAM,
SSD**, que además se usa como escritorio. Todo apunta a rendir en hardware
modesto.

## Presupuesto de RAM (15 GiB)

| Consumidor | RAM |
|---|---|
| SO + escritorio / familia (Firefox, streaming) | ~4.0 GiB reservados |
| Infra compartida (Caddy, Prometheus, Grafana, exporters, homepage, Postgres, Redis, Mailpit) | ~2.5 GiB |
| 5 equipos × 1.25 GiB máx | 6.25 GiB |
| **Total pico** | **~12.75 / 15 GiB** (≈2 GiB de aire) |

## Por equipo

| Recurso | Recomendado | Tope duro |
|---|---|---|
| RAM | 1 GiB | **1.25 GiB** |
| CPU | — | **1 núcleo** |
| Servicios | — | **5** |
| Disco | 15 GB (aviso) | **20 GB** |

La CPU se **sobre-suscribe** 5:4 a propósito: las cargas del lab son "a ráfagas",
y el kernel reparte el tiempo. El escritorio conserva prioridad.

## Cómo se aplican los topes (dos capas)

1. **Slice systemd por equipo** (cgroup v2). Cada equipo corre en
   `classroom-equipo-NN.slice` con `MemoryMax=1.25G`, `MemoryHigh=1G`,
   `CPUQuota=100%`, `TasksMax`. `labctld` corre los contenedores del equipo bajo
   `cgroup_parent=classroom-equipo-NN.slice`, así el **kernel capa a todo el
   equipo** sin importar lo que escriba el alumno.
2. **Límites en el Compose** (validados por la política): enseñan a escribir
   límites correctos y acotan cada servicio individual.

Verificado en producción: un contenedor de alumno aparece bajo
`/classroom.slice/…/classroom-equipo-01.slice/…` con `MemoryMax` aplicado.

## Disco (cuota dura)

El directorio de cada equipo (`/srv/classroom/equipo-NN`) es un **filesystem
loopback** del tamaño del tope duro (20 GB), montado `nosuid,nodev`. El equipo no
puede exceder físicamente su cupo. La política obliga a persistir **dentro** de
la carpeta, así todos los datos caen en ese filesystem con cuota. El umbral soft
(15 GB) se ve en `labctl usage` y en Grafana.

> Las **capas de imagen** de Docker se comparten entre equipos (`/var/lib/docker`)
> y se deduplican: si dos equipos usan `postgres:16.4-alpine`, se baja una vez.

## Observabilidad

Tres dashboards en Grafana (carpeta *Homelab*): **Classroom Overview**,
**Team Detail** (con selector de equipo), **Capacity Planning**. Métricas de
contenedores desde cAdvisor, del host desde node-exporter, agregadas por equipo
a partir del nombre de contenedor `equipo-NN-*`.
