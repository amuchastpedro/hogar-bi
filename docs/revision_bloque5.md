# Revisión del bloque 5 (disparador de Windows)

Aprobado el 2026-10-06: la persona usuaria comprobó los cinco puntos y confirmó las decisiones.

## Qué probó el agente (en una copia del proyecto, con `datos/` vacío)

- [x] Un PDF solo: se cargó solo tras la espera de 20 s.
- [x] Los 9 ejemplos a la vez: una sola ejecución de carga.
- [x] Un archivo que no es factura: código 1, va a `pendientes/` y se llama al punto de extensión.
- [x] Barrido (con el vigilante detenido) y desinstalación: no queda ninguna tarea ni proceso.
- [x] Tests del proyecto: 429 pasan.

## Qué falta evaluar (lo que el agente no pudo verificar)

Estado actual: el disparador está **instalado sobre el proyecto real** (`scripts\desinstalar_disparador.ps1` lo quita).

1. [x] `scripts\estado_disparador.ps1`: muestra las dos tareas instaladas y «Vigilante: corriendo».
2. [x] Copiar un PDF a `datos\entrada\`, esperar unos 30 s: se carga solo **y se ve el aviso de Windows** («1 factura cargada»). Con un PDF ya cargado (duplicado) no tiene que avisar.
3. [x] Cerrar sesión (o reiniciar), volver a entrar y ejecutar `estado_disparador.ps1`: el vigilante tiene que estar corriendo, sin ventana de consola.
4. [x] PC suspendida o apagada con PDFs en `entrada/`: al volver, el barrido (al iniciar sesión o a la hora) los procesa.
5. [x] Revisar `datos\logs\disparador.log`: que cuente lo ocurrido sin ruido.

## Decisiones a confirmar

- Espera por lotes de 20 s (`-EsperaSegundos` del vigilante) y barrido cada 60 min (`-MinutosBarrido` del instalador). ¿Sirven?
- El punto de extensión (`scripts\al_haber_pendientes.ps1`) se llama si esa ejecución rechazó algo, no según el código de salida.
- Sin tests de Python: la lógica está en PowerShell y se probó con las tareas reales.
- Si se mueve la carpeta del proyecto, hay que desinstalar y reinstalar (las tareas guardan la ruta).

## Para el bloque 6

`al_haber_pendientes.ps1` corre con el turno de carga tomado: debe lanzar el agente en segundo plano y volver enseguida (ficha 06).

## Al aprobar

Commit `bloque 5: disparador de Windows (vigilante, barrido, notificaciones)`; marcar el bloque como aprobado en `bitacora.md`; después `/clear` y bloque 6, parte A (Opus, esfuerzo medio).
