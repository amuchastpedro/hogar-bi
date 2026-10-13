# Caso: gastos de servicios del hogar

Archivo de caso para [`tarea.md`](tarea.md). Define todo lo específico de este caso.

No contiene datos personales. Los identificadores (números de contrato, de línea, de factura y CUPS) se leen de los PDFs al cargar y viven solo en la base, que está fuera de git.

## Contexto

- Una vivienda en Barcelona (España). Las facturas están en español y en euros.
- Proveedores actuales:
  - Aigües de Barcelona: agua.
  - Naturgy: gas y luz, en facturas separadas.
  - Digi: fibra y móvil, en una misma factura.
- Hay unos dos años de facturas históricas con los mismos formatos que los ejemplos. Se cargarán al terminar los bloques, dejándolas en `datos/entrada/`.
- En `ejemplos/` hay un PDF por formato: `agua.pdf`, `gas.pdf`, `luz.pdf` y `fibra_movil.pdf`.

## Parámetros del caso

Valores concretos de lo que `tarea.md` deja abierto.

| Parámetro | Valor en este caso |
|---|---|
| Herramienta del dashboard | Streamlit. Se construirá después de los bloques. |
| Moneda admitida (R42) | `EUR` |
| Identificador fiscal del proveedor (R20) | NIF español. Se normaliza en mayúsculas y sin guiones ni espacios. |
| Formato de los importes | Español: `1.234,56`. Los formatos de fecha varían según el proveedor (ver "Particularidades de cada formato"). |
| Extremos del período (R23) | Gas, luz y fibra y móvil: inclusivos (en gas y luz, los días impresos coinciden con fin − inicio + 1). Agua: el período impreso va de lectura a lectura y su primer día no se cuenta, así que inicio = fecha impresa + 1. Verificado: los promedios por día impresos en el ejemplo corresponden a 60 días, y la factura anterior termina el mismo día en que empieza la del ejemplo (09-abr-2026). |
| Identificador externo de cada contrato | Luz y gas: CUPS. Agua: nº de contrato. Móvil: nº de línea. Fibra: identificador de fibra. |
| Alias por defecto de un contrato (R21) | Nombre de la categoría y un número, por ejemplo "movil 1". |
| Atributos de contrato con vigencia (R22) | Luz: potencia contratada en P1 y P2. |
| Ejemplo resuelto del bloque 1 | `fibra_movil.pdf`, la factura más compleja: dos contratos de categorías distintas en un mismo documento. |
| Datos personales que busca el hook de git | DNI/NIE, IBAN, CUPS, teléfonos españoles y emails. Tampoco pueden versionarse números de contrato, de cliente ni de factura. Los NIF de los proveedores (tabla "Proveedores y formatos") sí pueden versionarse. |

## Copias de seguridad

- Destino: una carpeta dentro de Google Drive, sincronizada con Google Drive para escritorio (gratuito). El bloque 4 le pregunta la ruta exacta a la persona usuaria y la guarda en `datos/config.toml`, fuera de git.
- Las copias contienen las facturas y, por lo tanto, datos personales. Van a la cuenta de Google de la persona usuaria, y la carpeta no se comparte.
- Se conservan las últimas 30 instantáneas de la base.

## Preguntas que tiene que responder el dashboard

**Pestaña Overview: ¿cuánto gasto?**

- Gasto total y por categoría, o por cualquier combinación de categorías (selector múltiple).
- Períodos: un mes, un año, todo el histórico, el año en curso (YTD) y los últimos 12 meses.
- Scorecards con los totales del período elegido y un gráfico de evolución mensual.
- Los meses incompletos aparecen marcados.

**Pestañas de Análisis: una por categoría, salvo fibra y móvil, que comparten pestaña.** Son cuatro pestañas: agua, gas, luz, y fibra y móvil. Cada una responde "¿por qué esta categoría cuesta lo que cuesta?". En las pestañas de análisis, fibra y móvil se juntan, pero siguen siendo categorías separadas (en el Overview y en la base).

Contenido común a todas las pestañas:

- Desglose mensual del gasto por tipo de cargo: consumo, fijo y tasas e impuestos.
- Desglose por concepto dentro de cada tipo de cargo (por ejemplo, en luz, potencia P1 frente a P2).

Contenido específico de cada pestaña:

| Pestaña | Además del contenido común |
|---|---|
| agua | Evolución del volumen (m³) y del precio unitario efectivo. |
| gas | Evolución de la energía (kWh) y del precio unitario efectivo. Qué consumos vienen de lecturas estimadas y cuáles de lecturas reales. |
| luz | Evolución de la energía (kWh) y del precio unitario efectivo. Consumo por franja horaria (punta, llano y valle). Lecturas estimadas frente a reales. |
| fibra y móvil | El contenido común, con fibra y móvil por separado y su total. El consumo adicional del móvil ya aparece en el desglose por concepto. |

El precio unitario efectivo es el importe de los cargos de consumo dividido por el volumen. Sirve para distinguir entre "consumí más" y "subió el precio".

## Categorías de gasto

| Categoría | Proveedor actual | Magnitud de análisis | Unidad canónica | Periodicidad aproximada |
|---|---|---|---|---|
| `agua` | Aigües de Barcelona | volumen | m³ | bimestral |
| `gas` | Naturgy | energía | kWh (el PDF también informa m³ y el factor de conversión) | bimestral, irregular |
| `luz` | Naturgy | energía, por franja (punta, llano, valle) | kWh | mensual |
| `fibra` | Digi | — | — | mensual |
| `movil` | Digi | — | — | mensual |

- `agua` incluye las tasas de residuos que vienen en la factura del agua, aunque las cobren otros organismos. La categoría responde a "¿cuánto pagué en la factura del agua?".
- `fibra` y `movil` vienen en la misma factura de Digi, pero son categorías separadas.

## Tipos de cargo

| Tipo | Qué incluye |
|---|---|
| `consumo` | Cargos que dependen de lo que se consume. |
| `fijo` | Cargos que no dependen del consumo: cuotas, potencia contratada, alquileres. |
| `tasas_impuestos` | Tributos y tasas de organismos públicos, incluido el IVA, aunque se calculen sobre el consumo. |

## Clasificación de conceptos

Mapa inicial, que el bloque 1 convierte en semillas. Todos los conceptos de los ejemplos tienen imputación `periodo`.

| Categoría | Concepto | Tipo de cargo |
|---|---|---|
| agua | Cuota del servicio | fijo |
| agua | Consumo de agua (por tramos) | consumo |
| agua | Canon del agua, parte fija | tasas_impuestos |
| agua | Canon del agua, parte variable (por tramos) | tasas_impuestos |
| agua | Tasa de alcantarillado | tasas_impuestos |
| agua | Tasa de recogida de residuos municipales | tasas_impuestos |
| agua | Tasa metropolitana de tratamiento de residuos (TMTR) | tasas_impuestos |
| agua | IVA | tasas_impuestos |
| gas | Consumo de gas | consumo |
| gas | Término fijo | fijo |
| gas | Impuesto especial sobre hidrocarburos | tasas_impuestos |
| gas | IVA | tasas_impuestos |
| gas | Inspección periódica de la instalación | fijo |
| gas | Otros productos y servicios | fijo |
| luz | Consumo de electricidad | consumo |
| luz | Término de potencia P1 | fijo |
| luz | Término de potencia P2 | fijo |
| luz | Financiación del bono social | fijo |
| luz | Alquiler de contador | fijo |
| luz | Impuesto sobre la electricidad | tasas_impuestos |
| luz | IVA | tasas_impuestos |
| fibra | Cuota de fibra | fijo |
| fibra | IVA | tasas_impuestos |
| movil | Cuota del plan | fijo |
| movil | Consumo incluido en el plan (importe 0) | consumo |
| movil | Consumo adicional (SMS, llamadas o datos fuera del plan) | consumo |
| movil | IVA | tasas_impuestos |

La inspección periódica de la instalación de gas (gestión e inspección física) la aprobó la persona usuaria el 2026-10-06, con imputación `puntual`: se cobra una vez cada varios años.
"Otros productos y servicios" son servicios que Naturgy cobraba en la factura del gas de 2024 ("ServiElectric Xpress", con el IVA incluido): como las tasas de residuos en el agua, cuentan en la categoría de la factura que los cobra. Propuesto el 2026-10-06, con imputación `periodo`.

Pueden aparecer cargos que no están en los ejemplos: altas, penalizaciones, regularizaciones, descuentos. Cuando el plan B encuentre uno, propone el concepto con su tipo de cargo y su imputación (normalmente `puntual`) y lo marca para que lo decida la persona usuaria.

## Proveedores y formatos

| Proveedor | NIF | Formato | Categorías | Ejemplo |
|---|---|---|---|---|
| Aigües de Barcelona, Empresa Metropolitana de Gestió del Cicle Integral de l'Aigua, S.A. | A66098435 | `aigues_agua` | agua | `agua.pdf` |
| Naturgy Clientes, S.A.U. | A67760876 | `naturgy_gas` | gas | `gas.pdf` |
| Naturgy Clientes, S.A.U. | A67760876 | `naturgy_luz` | luz | `luz.pdf` |
| DIGI Spain Telecom, S.A.U. | A84919760 | `digi_convergente` | fibra, movil | `fibra_movil.pdf` |

## Particularidades de cada formato

### Aigües de Barcelona (agua)

- La página 1 tiene el resumen y la página 2 el detalle de conceptos. Las líneas salen del detalle.
- Fechas en dos formatos: `23-jun-2026` (emisión) y `09-abr-26 / 08-jun-26` (período, con el año en dos dígitos).
- El período impreso va de la fecha de la lectura anterior a la de la actual, y la factura siguiente empieza en la fecha en que termina la anterior. El primer día no se cuenta: el período del ejemplo es del 10-abr al 08-jun (60 días), como confirman los promedios impresos (250 litros por día, J,KZ €/día, J,JK €/día de suministro).
- La factura cobra en nombre de terceros:
  - el canon del agua, de la Agència Catalana de l'Aigua;
  - el alcantarillado y la recogida de residuos, del Ayuntamiento de Barcelona;
  - la TMTR, del Área Metropolitana.
- El "TOTAL FACTURA" impreso (KQ,QX €) es solo la parte de Aigües. El total que hay que cuadrar es el **"TOTAL A PAGAR"** (ZX,KK €).
- El IVA (10%) se aplica solo al suministro de agua. El canon figura como "NS" (no sujeto) y las tasas no llevan IVA.
- El consumo y el canon se cobran por tramos. Cada tramo es una línea con su cantidad y su precio. Los umbrales forman parte del texto ("Tramo hasta 12 m³", "Tramo de 12 a 15 m³") y pueden cambiar con la tarifa, así que no deben generar conceptos nuevos (R31).
- Lecturas: la anterior y la actual con sus fechas, y la base de facturación ("Lectura Real").

### Naturgy (gas)

- La página 2 tiene el detalle de la factura, las lecturas y los datos de suministro. La página 4 está en blanco. Parte de la página 3 tiene texto ilegible (códigos), así que el parser no debe depender de ella.
- La lectura "desde" es del día anterior al inicio del período (29/04 frente a 30/04). Es normal.
- El contador mide m³, pero se factura en kWh = m³ × factor de conversión. Se guardan los tres valores, con kWh como unidad canónica.
- La lectura puede ser real o estimada. En el ejemplo, la lectura final es **estimada**.
- La "cuantía de peajes" y la "cuantía de cargos" (sección 5) son informativas y ya están incluidas en los precios: **no son líneas**.
- El gráfico de consumo histórico de la página 1 no se carga.

### Naturgy (luz)

- La página 2 tiene el detalle, las lecturas y los datos de suministro. Las páginas 3 y 4 son informativas.
- La potencia se calcula como kW contratados × días × €/kW·día. Se guarda con cantidad = kW × días, en kW·día.
- El impuesto sobre la electricidad es un porcentaje sobre el subtotal (base JZ,KX €). El alquiler del contador va después y no forma parte de esa base.
- El consumo se cobra a un precio único, pero las lecturas vienen separadas en punta, llano y valle, cada una real o estimada.
- La potencia contratada (P1 y P2) es un atributo del contrato con vigencia (R22).
- La "cuantía de peajes", la "cuantía de cargos" y las "potencias máximas demandadas" son informativas: no son líneas.

### Digi (fibra y móvil)

- Una factura con dos contratos. En la página 2, cada contrato tiene su bloque "Servicios: <identificador>": el número de la línea móvil y el identificador de la fibra. La página 1 los rotula como "EN EL MÓVIL" y "EN CASA".
- Los importes de las líneas de la página 2 son **sin IVA**. El IVA (21%) solo se imprime como total de la factura. Para repartirlo por contrato se usan los totales por servicio de la página 2 ("Total" con IVA menos "Total sin impuestos"), y esas líneas de IVA se marcan como derivadas (R5).
- Los nombres comerciales de los productos cambian con el tiempo ("100 GB + Ilimitadas", "Fibra PRO-DIGI 10 Gb") y el texto incluye el período entre paréntesis ("(15 Jul - 14 Ago)"). Ninguna de las dos cosas debe generar conceptos nuevos (R31). Por ejemplo, la sección del documento donde aparece la línea ("PRODUCTOS", "CONSUMO ADICIONAL") puede servir para identificar el concepto.
- "Llamadas incluidas en tu producto" (44:35, 0,00 €) es una línea de importe 0. Se guarda para conservar el detalle.
- La dirección que figura en "Datos de cliente" no es la de suministro. No se usa.

## Valores esperados de los ejemplos

Son la referencia para los tests. Los importes están en euros, tal como se imprimen; en la base se guardan en céntimos. Todas las líneas tienen imputación `periodo`.

**Importes en letras.** Los importes, las bases y los precios de las facturas reales no se versionan: acá cada cifra es una letra (el mismo importe lleva siempre las mismas letras, en todo el repositorio). Las mismas secciones con los valores reales están en `ejemplos/valores_esperados.md`, fuera de git como los PDFs, y las usan los tests que leen esos PDFs. Los tests de la base usan facturas ficticias con esta misma forma (`tests/datos_prueba.py`), con sus controles de prorrateo.

### `agua.pdf`

Formato `aigues_agua`. Período impreso 09-abr-26 / 08-jun-26; normalizado, del 2026-04-10 al 2026-06-08 (60 días). Emisión: 2026-06-23. Total a pagar: ZX,KK.

| # | Texto en el PDF | Cantidad | Precio | Importe | Concepto | Tipo de cargo |
|---|---|---|---|---|---|---|
| 1 | Cuota del servicio | — | — | QX,XX | Cuota del servicio | fijo |
| 2 | Tramo hasta 12 m³ (consumo) | 12 m³ | J,ZXXJ €/m³ | J,QJ | Consumo de agua | consumo |
| 3 | Tramo de 12 a 15 m³ (consumo) | 3 m³ | J,XJQZ €/m³ | X,ZJ | Consumo de agua | consumo |
| 4 | Parte Fija del Canon del Agua | — | — | Q,JZ | Canon, parte fija | tasas_impuestos |
| 5 | Tramo hasta 15 m³ (canon) | 15 m³ | Z,XQKX €/m³ | K,XZ | Canon, parte variable | tasas_impuestos |
| 6 | IVA del 10% de la base sujeta | base JK,ZZ | 10% | Q,ZZ | IVA | tasas_impuestos |
| 7 | Tasa de alcantarillado (tramo hasta 15 m³) | 15 m³ | Z,QZJQ €/m³ | J,QK | Tasa de alcantarillado | tasas_impuestos |
| 8 | Tasa de recogida residuos municipales generados en los domicilios | — | — | QZ,XX | Tasa de residuos municipales | tasas_impuestos |
| 9 | Tasa metropolitana tratamiento residuos municipales (T.M.T.R.) | — | — | ZJ,QZ | TMTR | tasas_impuestos |

Mediciones: 15 m³. Lectura anterior 642 (2026-04-09) y actual 657 (2026-06-08), real.

### `gas.pdf`

Formato `naturgy_gas`. Período del 2026-04-30 al 2026-06-25 (57 días). Emisión: 2026-06-29. Total a pagar: KJ,ZJ.

| # | Texto en el PDF | Cantidad | Precio | Importe | Concepto | Tipo de cargo |
|---|---|---|---|---|---|---|
| 1 | Consumo gas | 344 kWh | Z,KJXJXX €/kWh | KX,QZ | Consumo de gas | consumo |
| 2 | Impuesto Especial sobre hidrocarburos | 344 kWh | Z,JJKKKZ €/kWh | K,QK | Impuesto sobre hidrocarburos | tasas_impuestos |
| 3 | Término fijo | 57 días | Q,QJJKQX €/día | X,QX | Término fijo | fijo |
| 4 | IVA (21%) | base QX,JZ | 21% | K,XZ | IVA | tasas_impuestos |

Mediciones: 344 kWh = 30 m³ × 11,470 kWh/m³. Lectura anterior 15.547 m³ (2026-04-29, real) y actual 15.577 m³ (2026-06-25, **estimada**).

### `luz.pdf`

Formato `naturgy_luz`. Período del 2026-05-27 al 2026-06-28 (33 días). Emisión: 2026-07-03. Total a pagar: XJ,ZZ.

| # | Texto en el PDF | Cantidad | Precio | Importe | Concepto | Tipo de cargo |
|---|---|---|---|---|---|---|
| 1 | Consumo electricidad | 81 kWh | Q,XZKZXZ €/kWh | QQ,QX | Consumo de electricidad | consumo |
| 2 | Término potencia P1 | 4,4 kW × 33 días = 145,2 kW·día | Z,XZXQQZ €/kW·día | JJ,KK | Potencia P1 | fijo |
| 3 | Término potencia P2 | 145,2 kW·día | X,XZKXJK €/kW·día | Z,ZJ | Potencia P2 | fijo |
| 4 | Financiación de Bono Social | 33 días | X,KXZJXK €/día | Q,KJ | Bono social | fijo |
| 5 | Impuesto electricidad | base JZ,KX | 5,112696% | Q,XK | Impuesto sobre la electricidad | tasas_impuestos |
| 6 | Alquiler de contador | 33 días | J,ZZXZKX €/día | Q,QJ | Alquiler de contador | fijo |
| 7 | IVA (21%) | base XK,JZ | 21% | X,KK | IVA | tasas_impuestos |

Mediciones: todas reales, con lectura del 2026-06-28. Punta 20 kWh, llano 21 kWh, valle 40 kWh; total 81 kWh.

Contrato: potencia contratada de 4,4 kW en P1 y 4,4 kW en P2.

### `fibra_movil.pdf`

Formato `digi_convergente`. Período del 2026-07-15 al 2026-08-14 (31 días). Emisión: 2026-08-21. Vencimiento: 2026-08-28. Total a pagar: XX,XZ (base XQ,JJ + IVA X,QK).

| # | Contrato | Texto en el PDF | Cantidad | Importe | Concepto | Tipo de cargo |
|---|---|---|---|---|---|---|
| 1 | movil | 100 GB + Ilimitadas (15 Jul - 14 Ago) | 1 | Z,XQ | Cuota del plan | fijo |
| 2 | movil | Llamadas incluidas en tu producto | 44:35 min | 0,00 | Consumo incluido | consumo |
| 3 | movil | SMS (consumo adicional) | 1 | Z,QK | Consumo adicional | consumo |
| 4 | movil | IVA 21% (derivada) | base Z,KQ | Q,JX | IVA | tasas_impuestos |
| 5 | fibra | Fibra PRO-DIGI 10 Gb (15 Jul - 14 Ago) | 1 | QK,KQ | Cuota de fibra | fijo |
| 6 | fibra | IVA 21% (derivada) | base QK,KQ | X,ZZ | IVA | tasas_impuestos |

Totales por categoría: `movil` X,QZ y `fibra` ZX,ZJ.

## Controles de prorrateo y cobertura

Con solo los cuatro ejemplos cargados. Los repartos mensuales son aproximados (±1 céntimo), pero la suma de cada factura tiene que ser exacta. Los importes van en letras, como en la sección anterior.

| Factura | Reparto mensual |
|---|---|
| agua (ZX,KK) | abril, 21 días ≈ ZZ,JK · mayo, 31 días ≈ ZK,KX · junio, 8 días ≈ X,KJ |
| gas (KJ,ZJ) | abril, 1 día ≈ J,XZ · mayo, 31 días ≈ QZ,ZJ · junio, 25 días ≈ ZK,KJ |
| luz (XJ,ZZ) | mayo, 5 días ≈ X,ZK · junio, 28 días ≈ XQ,XK |
| movil (X,QZ) | julio, 17 días ≈ Z,JX · agosto, 14 días ≈ X,JQ |
| fibra (ZX,ZJ) | julio, 17 días ≈ JK,XK · agosto, 14 días ≈ XJ,JX |

Cobertura en mayo de 2026: agua y gas, completos (31/31); luz, incompleto (5/31). En junio de 2026, las tres son incompletas: agua 8/30, gas 25/30 y luz 28/30.
