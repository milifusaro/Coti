"""
Chequea la diferencia entre:
  - Comprar dolares en Uala ("Compras a" en comparadolar.ar/usd/uala)
  - Vender dolares en Fiwind ("Vendes a" en comparadolar.ar/usd/fiwind-cripto)

Ambos precios se extraen del HTML publico de ComparaDolar.ar, que muestra
datos en tiempo real (confirmados contra las apps reales de Uala y Fiwind).

Si la ganancia en pesos por dolar supera el umbral (THRESHOLD_ARS), manda un
mensaje por Telegram.

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

UALA_URL = "https://comparadolar.ar/usd/uala"
FIWIND_URL = "https://comparadolar.ar/usd/fiwind-cripto"
TELEGRAM_API_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"

# Numeros con formato argentino: 1.510,00 (despues de la etiqueta "Compras a" / "Vendes a")
COMPRAS_PATTERN = re.compile(r"Compras a.{0,150}?([\d]{1,3}(?:\.\d{3})*,\d{2})", re.DOTALL)
VENDES_PATTERN = re.compile(r"Vendes a.{0,150}?([\d]{1,3}(?:\.\d{3})*,\d{2})", re.DOTALL)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}


def parse_ar_number(text: str) -> float:
    """Convierte '1.510,00' (formato argentino) a 1510.00 (float)."""
    return float(text.replace(".", "").replace(",", "."))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def strip_html_tags(html: str) -> str:
    """Saca todas las etiquetas HTML y colapsa espacios, para que la
    etiqueta ('Compras a') y el numero queden cerca en el texto plano."""
    sin_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", sin_tags)


def solo_seccion_principal(texto_plano: str) -> str:
    """Corta el texto antes de la lista 'Otras opciones para operar USD',
    para no confundir el precio de la entidad principal con el de otro
    proveedor listado mas abajo en la misma pagina."""
    corte = texto_plano.find("Otras opciones")
    return texto_plano if corte == -1 else texto_plano[:corte]


def get_uala_compra() -> float:
    """Precio al que Uala te vende dolares (lo que vos pagas al comprar)."""
    html = fetch_text(UALA_URL)
    seccion = solo_seccion_principal(strip_html_tags(html))
    match = COMPRAS_PATTERN.search(seccion)
    if not match:
        raise RuntimeError(
            "No se pudo encontrar el precio de 'Compras a' en la pagina de Uala. "
            "La pagina puede haber cambiado de estructura."
        )
    return parse_ar_number(match.group(1))


def get_fiwind_venta() -> float:
    """Precio al que Fiwind te compra dolares (lo que vos recibis al vender)."""
    html = fetch_text(FIWIND_URL)
    seccion = solo_seccion_principal(strip_html_tags(html))
    match = VENDES_PATTERN.search(seccion)
    if not match:
        raise RuntimeError(
            "No se pudo encontrar el precio de 'Vendes a' en la pagina de Fiwind. "
            "La pagina puede haber cambiado de estructura."
        )
    return parse_ar_number(match.group(1))


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

    uala_compra = get_uala_compra()
    fiwind_venta = get_fiwind_venta()

    ganancia_ars_por_usd = fiwind_venta - uala_compra
    ganancia_pct = (ganancia_ars_por_usd / uala_compra) * 100

    print(f"Uala (comprás a):     {uala_compra:.2f} ARS/USD")
    print(f"Fiwind (vendés a):    {fiwind_venta:.2f} ARS/USD")
    print(f"Ganancia:             {ganancia_ars_por_usd:.2f} ARS/USD ({ganancia_pct:.2f}%)")

    if ganancia_ars_por_usd >= threshold_ars:
        mensaje = (
            f"🟢 <b>Oportunidad detectada</b>\n\n"
            f"Comprar en Uala: <b>{uala_compra:.2f}</b> ARS/USD\n"
            f"Vender en Fiwind: <b>{fiwind_venta:.2f}</b> ARS/USD\n"
            f"Ganancia: <b>{ganancia_ars_por_usd:.2f} ARS por dolar ({ganancia_pct:.2f}%)</b>\n\n"
            f"(Umbral configurado: ${threshold_ars:.2f} por dolar)"
        )
        send_telegram_message(bot_token, chat_id, mensaje)
        print("Notificacion enviada.")
    else:
        print("Diferencia por debajo del umbral, no se notifica.")


if __name__ == "__main__":
    main()
