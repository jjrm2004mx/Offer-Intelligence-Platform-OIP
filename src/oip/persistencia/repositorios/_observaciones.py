"""Filas de una observación (TAB-04 a TAB-08) y la observación desde sus filas (CMP-20)."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Table,
)

from oip.catalogos import Categoria
from oip.entradas.contrato import Observacion
from oip.evaluacion.contexto import (
    ObservacionRegistrada,
)
from oip.persistencia import tablas
from oip.persistencia.repositorios._columnas import (
    Fila,
    enum_o_none,
    json_o_none,
    leer_json_o_none,
    normalizar,
    utc,
)
from oip.persistencia.repositorios._tipos import (
    ErrorRepositorio,
    IdentificadorProducto,
    ObservacionNueva,
    Producto,
    Publicacion,
)

# --- TAB-03 y TAB-04 ----------------------------------------------------------------------


def fila_producto(producto: Producto) -> Fila:
    return normalizar(
        tablas.product,
        {
            "id": producto.id,
            "brand": producto.marca,
            "model": producto.modelo,
            "content": producto.contenido,
            "category": producto.categoria,
            "created_at": producto.creado_en,
        },
    )


def producto_de_fila(fila: Mapping[str, Any]) -> Producto:
    return Producto(
        id=fila["id"],
        creado_en=utc(fila["created_at"]),
        marca=fila["brand"],
        modelo=fila["model"],
        contenido=fila["content"],
        categoria=enum_o_none(Categoria, fila["category"]),
    )


def fila_identificador(identificador: IdentificadorProducto, id_producto: Any) -> Fila:
    return normalizar(
        tablas.product_identifier,
        {"kind": identificador.clase, "value": identificador.valor, "product_id": id_producto},
    )


def fila_publicacion(publicacion: Publicacion) -> Fila:
    return normalizar(
        tablas.listing,
        {
            "id": publicacion.id,
            "product_id": publicacion.id_producto,
            "retailer_code": publicacion.comercio,
            "store_code": publicacion.tienda,
            "canonical_url": publicacion.url_canonica,
            "platform": publicacion.plataforma,
            "pickup_location": publicacion.ciudad_recogida,
            "first_seen_at": publicacion.vista_por_primera_vez,
        },
    )


def publicacion_de_fila(fila: Mapping[str, Any]) -> Publicacion:
    return Publicacion(
        id=fila["id"],
        id_producto=fila["product_id"],
        comercio=fila["retailer_code"],
        url_canonica=fila["canonical_url"],
        vista_por_primera_vez=utc(fila["first_seen_at"]),
        tienda=fila["store_code"],
        plataforma=fila["platform"],
        ciudad_recogida=fila["pickup_location"],
    )


# --- TAB-05 a TAB-08: observación ---------------------------------------------------------


def filas_observacion(nueva: ObservacionNueva) -> list[tuple[Table, Fila]]:
    """Las filas de una observación nueva, en orden de inserción: recibo (TAB-08), producto,
    identificadores y publicación nuevos, y TAB-05, TAB-06 y, si es ficha, TAB-07."""
    if not isinstance(nueva, ObservacionNueva):
        raise TypeError("nueva: se esperaba ObservacionNueva")
    r = nueva.registrada
    o = r.observacion
    filas: list[tuple[Table, Fila]] = [
        (
            tablas.ingest_receipt,
            normalizar(
                tablas.ingest_receipt,
                {
                    "idempotency_key": nueva.clave_idempotencia,
                    "observation_id": r.id,
                    "source": nueva.origen,
                    "received_at": nueva.recibida_en,
                    "load_run_id": nueva.id_carga,
                },
            ),
        )
    ]
    if nueva.producto is not None:
        filas.append((tablas.product, fila_producto(nueva.producto)))
    filas.extend(
        (tablas.product_identifier, fila_identificador(i, r.id_producto))
        for i in nueva.identificadores
    )
    if nueva.publicacion is not None:
        filas.append((tablas.listing, fila_publicacion(nueva.publicacion)))
    msrp = o.msrp
    precio = {
        "observation_id": r.id,
        "observed_at": o.extracted_at,
        "listing_id": r.id_publicacion,
        "product_id": r.id_producto,
        "price": o.price.current,
        "was_price": o.price.was,
        "currency": o.price.currency,
        "seller": o.seller,
        "condition": o.condition,
        "purchase_mode": o.purchase_mode,
        "is_clearance": o.is_clearance,
        "tax_location": o.tax_location,
        "shipping_to_me": None if o.shipping is None else o.shipping.to_me_cost,
        "weight_kg": o.weight_kg,
        "dims_cm": json_o_none(o.dims_cm, dict[str, Decimal]),
        "category": o.category,
        "title": o.title,
        "identification": nueva.identificacion,
        "msrp_value": None if msrp is None else msrp.value,
        "msrp_source": None if msrp is None else msrp.source,
        "msrp_date": None if msrp is None else msrp.date,
        "schema_version": o.schema_version,
        "source_type": o.source_type,
        "extraction_method": o.extraction_method,
        "load_run_id": nueva.id_carga,
    }
    filas.append((tablas.price_observation, normalizar(tablas.price_observation, precio)))
    a = o.availability
    disponibilidad = {
        "observation_id": r.id,
        "observed_at": o.extracted_at,
        "listing_id": r.id_publicacion,
        "store_code": o.store_code,
        "state": a.state,
        "quantity": a.quantity,
        "text": a.text,
        "scope": a.scope,
        "add_to_cart": a.add_to_cart,
    }
    filas.append(
        (
            tablas.availability_observation,
            normalizar(tablas.availability_observation, disponibilidad),
        )
    )
    f = o.amazon_listing
    if f is not None:
        ficha = {
            "observation_id": r.id,
            "observed_at": o.extracted_at,
            "product_id": r.id_producto,
            "listing_id": r.id_publicacion,
            "buy_box_price": f.buy_box_price,
            "sellers_new": f.sellers_new,
            "rank_main": f.rank_main,
            "rank_sub": f.rank_sub,
            "reviews": f.reviews,
            "bought_last_month": f.bought_last_month,
        }
        filas.append(
            (
                tablas.amazon_listing_observation,
                normalizar(tablas.amazon_listing_observation, ficha),
            )
        )
    return filas


def _sin_nulos(datos: Mapping[str, Any]) -> dict[str, Any] | None:
    salida = {k: v for k, v in datos.items() if v is not None}
    return salida or None


def observacion_de_filas(
    precio: Mapping[str, Any],
    disponibilidad: Mapping[str, Any],
    publicacion: Mapping[str, Any],
    ficha: Mapping[str, Any] | None,
) -> ObservacionRegistrada:
    """La observación tal como la guardan sus columnas (TAB-04 a TAB-07).

    Vuelven igual: precio, vendedor, estado, modo de compra, liquidación, ubicación del
    impuesto, envío hacia mí, peso, medidas, categoría, título, MSRP, ``schemaVersion``,
    ``sourceType``, ``extractionMethod``, la disponibilidad completa, la ficha de Amazon y
    ``extractedAt`` (en UTC). Comercio, URL (la **canónica**) y ciudad de recogida salen de
    la publicación (TAB-04); ``storeCode``, de la disponibilidad. ``blocked`` es falso (una
    observación bloqueada no se guarda). **Sin columna** (vuelven ausentes):
    ``crawlJobId``, ``idempotencyKey`` (está en TAB-08), ``brand``, ``model``, ``gtin`` y
    ``content`` (son del producto, TAB-03), ``shipping.days``, ``shipping.mode`` y
    ``evidence``. El contexto exacto de una evaluación está en su ``input_snapshot``.
    """
    msrp = _sin_nulos(
        {
            "value": precio["msrp_value"],
            "source": precio["msrp_source"],
            "date": precio["msrp_date"],
        }
    )
    datos: dict[str, Any] = {
        "schemaVersion": precio["schema_version"],
        "retailerCode": publicacion["retailer_code"],
        "storeCode": disponibilidad["store_code"],
        "sourceType": precio["source_type"],
        "productUrl": publicacion["canonical_url"],
        "title": precio["title"],
        "category": precio["category"],
        "weightKg": precio["weight_kg"],
        "dimsCm": leer_json_o_none(precio["dims_cm"], dict[str, Decimal]),
        "price": {
            "current": precio["price"],
            "was": precio["was_price"],
            "currency": precio["currency"],
        },
        "seller": precio["seller"],
        "condition": precio["condition"],
        "availability": {
            "state": disponibilidad["state"],
            "text": disponibilidad["text"],
            "quantity": disponibilidad["quantity"],
            "scope": disponibilidad["scope"],
            "addToCart": disponibilidad["add_to_cart"],
        },
        "isClearance": precio["is_clearance"],
        "purchaseMode": precio["purchase_mode"],
        "taxLocation": precio["tax_location"],
        "pickupLocation": publicacion["pickup_location"],
        "shipping": None
        if precio["shipping_to_me"] is None
        else {"toMeCost": precio["shipping_to_me"]},
        "msrp": msrp,
        "amazonListing": None
        if ficha is None
        else {
            "buyBoxPrice": ficha["buy_box_price"],
            "sellersNew": ficha["sellers_new"],
            "rankMain": ficha["rank_main"],
            "rankSub": ficha["rank_sub"],
            "reviews": ficha["reviews"],
            "boughtLastMonth": ficha["bought_last_month"],
        },
        "extractedAt": utc(precio["observed_at"]),
        "extractionMethod": precio["extraction_method"],
        "blocked": False,
    }
    try:
        observacion = Observacion.model_validate(datos)
    except ValueError:
        # Sin el detalle de pydantic: podría citar un valor.
        raise ErrorRepositorio("price_observation: la fila no forma una observación") from None
    return ObservacionRegistrada(
        observacion, precio["observation_id"], precio["listing_id"], precio["product_id"]
    )
