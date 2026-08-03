"""
Chequea la diferencia entre:
  - Comprar dolar oficial en Uala (proxy: DolarApi, casa "oficial", precio de venta)
  - Vender dolares en Fiwind, producto "Dolar 24/7"
    (fuente: pagina publica de InfoDolar, que refleja ese mismo precio)

Si la ganancia porcentual supera el umbral (THRESHOLD_PCT), manda un mensaje
por Telegram.

Variables de entorno necesarias:
  TELEGRAM_BOT_TOKEN  -> token del bot (te lo da @BotFather)
  TELEGRAM_CHAT_ID    -> tu chat id (te lo da @userinfobot)
  THRESHOLD_ARS       -> opcional, default 4.0 (ganancia minima en ARS por USD)
"""

import os
import re
import sys
import json
import urllib.request
import urllib.error

DOLARAPI_OFICIAL_URL = "https://dolarapi.com/v1/dolares/oficial"
INFODOLAR_FIWIND_URL = "https://www.infodolar.com/cotizacion-dolar-entidad-fiwind.aspx"
TELEGRAM_API_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"

# Numeros con formato argentino: $ 1.504,80  o  $ 4,80
MONEY_PATTERN = re.compile(r"\$\s*([\d]{1,3}(?:\.\d{3})*,\d{2})")


def parse_ar_number(text: str) -> float:
    """Convierte '1.504,80' (formato argentino) a 1504.80 (float)."""
    return float(text.replace(".", "").replace(",", "."))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "arbitraje-dolar-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_uala_venta() -> float:
    """Precio al que Uala te vende dolar oficial (lo que vos pagas)."""
    data = fetch_json(DOLARAPI_OFICIAL_URL)
    return float(data["venta"])


def get_fiwind_compra() -> float:
    """
    Precio al que Fiwind te compra dolares en su producto 'Dolar 24/7'
    (lo que vos recibis al vender). Se extrae del HTML de InfoDolar.

    Estructura esperada en la fila de la tabla (en orden de aparicion):
      1) precio de Compra
      2) variacion en $ de Compra
      3) precio de Venta
      4) variacion en $ de Venta
      5) precio de la columna "30%"
      ... (variacion %, spread, etc.)
    """
    html = fetch_text(INFODOLAR_FIWIND_URL)

    # Nos quedamos con el tramo que contiene la tabla de cotizacion,
    # para no confundirnos con otros montos que pueda haber en la pagina.
    marker_start = html.upper().find("COTIZACI")
    marker_end = html.find("Puede ser de tu inter")
    if marker_start == -1 or marker_end == -1 or marker_end <= marker_start:
        raise RuntimeError(
            "No se pudo ubicar la tabla de cotizacion en el HTML de InfoDolar. "
            "Puede que la pagina haya cambiado de estructura."
        )
    seccion = html[marker_start:marker_end]

    montos = MONEY_PATTERN.findall(seccion)
    if len(montos) < 3:
        raise RuntimeError(
            f"Se esperaban al menos 3 montos en la tabla y se encontraron {len(montos)}. "
            "La pagina puede haber cambiado de estructura."
        )

    precio_compra = parse_ar_number(montos[0])
    return precio_compra


def send_telegram_message(token: str, chat_id: str, text: str) -> None:
    url = TELEGRAM_API_TEMPLATE.format(token=token)
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"Error enviando mensaje a Telegram: {e.read().decode('utf-8')}", file=sys.stderr)
        raise


def main() -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    threshold_ars = float(os.environ.get("THRESHOLD_ARS", "4.0"))

    if not bot_token or not chat_id:
        print("Faltan TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID en las variables de entorno.", file=sys.stderr)
        sys.exit(1)

    uala_venta = get_uala_venta()
    fiwind_compra = get_fiwind_compra()

    ganancia_ars_por_usd = fiwind_compra - uala_venta
    ganancia_pct = (ganancia_ars_por_usd / uala_venta) * 100

    print(f"Uala (venta oficial):     {uala_venta:.2f} ARS/USD")
    print(f"Fiwind (compra 24/7):     {fiwind_compra:.2f} ARS/USD")
    print(f"Ganancia:                 {ganancia_ars_por_usd:.2f} ARS/USD ({ganancia_pct:.2f}%)")

    if ganancia_ars_por_usd >= threshold_ars:
        mensaje = (
            f"🟢 <b>Oportunidad detectada</b>\n\n"
            f"Comprar en Uala: <b>{uala_venta:.2f}</b> ARS/USD\n"
            f"Vender en Fiwind: <b>{fiwind_compra:.2f}</b> ARS/USD\n"
            f"Ganancia: <b>{ganancia_ars_por_usd:.2f} ARS por dolar ({ganancia_pct:.2f}%)</b>\n\n"
            f"(Umbral configurado: ${threshold_ars:.2f} por dolar)"
        )
        send_telegram_message(bot_token, chat_id, mensaje)
        print("Notificacion enviada.")
    else:
        print("Diferencia por debajo del umbral, no se notifica.")


if __name__ == "__main__":
    main()
