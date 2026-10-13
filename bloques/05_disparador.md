# Bloque 5: Disparador de Windows

## Objetivo

Que Windows ejecute la carga solo cuando aparecen PDFs en `datos/entrada/`, sin que la persona usuaria tenga que abrir nada.

## Antes de empezar

Leer `docs/estado.md` y la ficha del bloque (`docs/fichas/05_disparador.md`), que dice qué secciones hacen falta; `CLAUDE.md` y `tarea.md` se leen siempre. Si la ficha no existe, leer las secciones «Comandos» y «Requisitos de la ejecución» del bloque 4.

## Requisitos

- **Reacción rápida:** un PDF nuevo se procesa en pocos minutos.
- **Por evento, con barrido de respaldo:**
  - un vigilante de la carpeta (por ejemplo, un `FileSystemWatcher` de PowerShell que el Programador de tareas inicia al iniciar sesión);
  - un barrido periódico (por ejemplo, cada hora y al iniciar sesión), que procesa lo que el vigilante no vio o lo que se dejó con la PC apagada.
- **Por lotes:** después del último archivo nuevo, se espera un rato sin novedades antes de lanzar la carga. Dejar 500 PDFs de golpe produce una ejecución, no 500.
- **Sin ejecuciones simultáneas**, además del bloqueo propio de la carga (bloque 4).
- **Invisible:** no aparece ninguna ventana de consola.
- **Sin permisos de administrador:** la tarea programada es a nivel de usuario. No se cambia la política de ejecución de PowerShell del sistema; si hace falta, se indica solo en la línea de comandos de la tarea.
- **Notificaciones de Windows** (gratuitas y sin administrador) al terminar una carga que cargó o rechazó algo, por ejemplo: "3 facturas cargadas, 1 pendiente". Si no pasó nada, no se notifica.
- **Punto de extensión para el plan B:** si la carga termina con código `1` (pendientes nuevos), ejecutar `scripts/al_haber_pendientes.ps1`, si existe. Este bloque no depende del bloque 6.
- **Rutas:** el instalador resuelve la ruta del proyecto al instalar. No hay rutas fijas en el código.
- **Logs** del vigilante en `datos/logs/`.

## Scripts

- `scripts/instalar_disparador.ps1`: idempotente; instalarlo dos veces no duplica nada.
- `scripts/desinstalar_disparador.ps1`.
- `scripts/estado_disparador.ps1`: muestra si está instalado, si el vigilante está corriendo, y la última ejecución con su resultado.

## Criterios de aceptación

Pruebas que hace el agente:

- Tras instalar, un PDF de ejemplo dejado en `datos/entrada/` se procesa solo y llega la notificación.
- Al dejar todos los ejemplos a la vez, hay una sola ejecución de carga.
- Un PDF que no es una factura va a pendientes, llega la notificación y se llama al punto de extensión (se prueba con un script de prueba).
- Después de desinstalar, no queda ninguna tarea ni ningún proceso.

Para el punto de control, dejar instrucciones para que la persona usuaria pruebe lo que el agente no puede: cerrar sesión o reiniciar, y comprobar que sigue funcionando.

## Fuera de este bloque

El plan B (bloque 6).
