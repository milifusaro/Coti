# Alerta de arbitraje Ualá (dólar oficial) ↔ Fiwind (dólar cripto)

Te avisa por Telegram cuando la diferencia entre comprar dólar oficial en Ualá
y venderlo como dólar cripto en Fiwind supera un umbral configurable.

## Cómo funciona
- **Precio de compra (Ualá)**: se usa la cotización pública del dólar oficial
  (venta) de [DolarApi](https://dolarapi.com), ya que Ualá cobra ese mismo
  valor sin comisión adicional.
- **Precio de venta (Fiwind)**: se usa el precio "Compra" (lo que te pagan a
  vos al vender) del producto "Dólar 24/7" de Fiwind, extraído directamente
  del HTML público de [InfoDolar](https://www.infodolar.com/cotizacion-dolar-entidad-fiwind.aspx),
  que refleja ese mismo valor con pocos minutos de atraso.
- Cada 15 minutos, GitHub Actions corre el script `check_arbitrage.py`. Si la
  ganancia porcentual es mayor o igual al umbral, te manda un mensaje de
  Telegram.

> ⚠️ Nota 1: el precio real que te ofrece Ualá o Fiwind al momento de
> confirmar la operación puede variar levemente. Este chequeo es una
> aproximación para avisarte cuándo vale la pena abrir la app y confirmar el
> valor exacto.
>
> ⚠️ Nota 2: como Fiwind no tiene una API pública oficial para este precio,
> el script lee el HTML de InfoDolar y busca los montos en el orden en que
> aparecen hoy. Si InfoDolar cambia el diseño de esa página en el futuro, el
> script puede empezar a fallar — el error va a aparecer en la pestaña
> "Actions" de tu repo, avisame si eso pasa y lo ajustamos.

## Paso 1: Crear tu bot de Telegram (2 minutos)
1. Abrí Telegram y buscá **@BotFather**.
2. Enviale `/newbot`, elegí un nombre y un usuario (debe terminar en `bot`).
3. Te va a dar un **token** con este formato: `123456789:ABCdefGhIJKlmNoPQRstuVWXyz`.
   Guardalo, es tu `TELEGRAM_BOT_TOKEN`.
4. Buscá **@userinfobot** en Telegram, enviale cualquier mensaje y te va a
   devolver tu **Chat ID** (un número). Ese es tu `TELEGRAM_CHAT_ID`.
5. Importante: enviale **cualquier mensaje** a tu bot recién creado (buscalo
   por el usuario que le pusiste) para "activar" la conversación — si no,
   no puede enviarte mensajes.

## Paso 2: Subir esto a GitHub
1. Creá un repositorio nuevo en GitHub (puede ser privado).
2. Subí estos archivos (`check_arbitrage.py`, la carpeta `.github/`, y este
   README) al repositorio. Podés arrastrarlos directamente desde la web de
   GitHub ("Add file" → "Upload files") si no usás git desde la terminal.

## Paso 3: Configurar los secretos
1. En tu repositorio, entrá a **Settings → Secrets and variables → Actions**.
2. Creá dos secretos:
   - `TELEGRAM_BOT_TOKEN` → el token del Paso 1.
   - `TELEGRAM_CHAT_ID` → tu chat id del Paso 1.

## Paso 4: Listo
- El workflow ya corre solo cada 15 minutos.
- Para probarlo ahora mismo sin esperar: entrá a la pestaña **Actions** de tu
  repo, elegí el workflow "Chequear arbitraje dolar Uala/Fiwind" y tocá
  **"Run workflow"**.

## Ajustar el umbral o la frecuencia
- Umbral de ganancia: cambiá `THRESHOLD_ARS` en `.github/workflows/check.yml`
  (está en 4.0 = te avisa solo si la ganancia es de $4 o más por dólar).
- Frecuencia: cambiá el `cron` en el mismo archivo. Por ejemplo, `*/5 * * * *`
  corre cada 5 minutos (GitHub puede demorar un poco más en horarios de alta
  demanda, es normal).

## Correrlo en tu PC en vez de GitHub Actions (alternativa)
Si prefieres no usar GitHub, podés correr `check_arbitrage.py` con Python 3
directamente en tu computadora, seteando las variables de entorno
`TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`, y usando el Programador de tareas
(Windows) o `cron` (Mac/Linux) para que corra cada 15 minutos. Avisame si
querés que te arme esa versión.
