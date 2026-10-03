"""The merchant's world: orders, payments, shipments, emails and open disputes.

Hot Spring Supply Co. is fictional. Every record is generated relative to the
moment the backend starts so deadlines always count down and Visa's
Compelling Evidence 3.0 windows (prior orders 120-365 days old) always hold.

Some evidence deliberately lives outside the merchant's systems:
- proof-of-delivery photos belong to the ShipCo warehouse (a partner agent on Band)
- the StormShell lab report sits in the merchant's own files until they share it
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


def iso(ts: datetime) -> str:
    return ts.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


MERCHANT = {
    "name": "Hot Spring Supply Co.",
    "owner": "You",
    "site": "hotspringsupply.example",
    "refund_policy": (
        "30-day returns on unused items. Refunds are issued to the original payment method "
        "within 5 business days of receiving the return."
    ),
    "terms_acceptance": "Customers tick 'I agree to the Terms & Refund Policy' before paying.",
}

REASONS = {
    "product_not_received": {"network_code": "Visa 13.1", "label": "Not received"},
    "fraudulent": {"network_code": "Visa 10.4", "label": "Fraud (card absent)"},
    "subscription_canceled": {"network_code": "Visa 13.2", "label": "Cancelled recurring"},
    "product_unacceptable": {"network_code": "Visa 13.3", "label": "Not as described"},
    "duplicate": {"network_code": "Visa 12.6.1", "label": "Duplicate charge"},
}


@dataclass
class World:
    now: datetime
    customers: dict[str, dict[str, Any]] = field(default_factory=dict)
    orders: dict[str, dict[str, Any]] = field(default_factory=dict)
    shipments: dict[str, dict[str, Any]] = field(default_factory=dict)  # ShipCo-held
    support: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    subscriptions: dict[str, dict[str, Any]] = field(default_factory=dict)
    refunds: dict[str, dict[str, Any]] = field(default_factory=dict)  # by charge id
    disputes: dict[str, dict[str, Any]] = field(default_factory=dict)
    merchant_files: dict[str, dict[str, Any]] = field(default_factory=dict)

    def ago(self, days: float, hour: int | None = None, minute: int = 0) -> datetime:
        ts = self.now - timedelta(days=days)
        if hour is not None:
            ts = ts.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return ts

    def ahead(self, days: float, hours: float = 0) -> datetime:
        return self.now + timedelta(days=days, hours=hours)

    # ---- lookups used by the inspector's tools ---------------------------------

    def customer_history(self, email: str) -> list[dict[str, Any]]:
        disputed_charges = {d["charge_id"] for d in self.disputes.values()}
        rows = []
        for order in sorted(self.orders.values(), key=lambda o: o["placed_at"]):
            if order["customer_email"] != email:
                continue
            pay = order["payment"]
            rows.append(
                {
                    "order_id": order["id"],
                    "placed_at": order["placed_at"],
                    "total": order["total"],
                    "items": [i["name"] for i in order["items"]],
                    "charge_id": pay["charge_id"],
                    "card": f"{pay['card_brand']} •••• {pay['last4']}",
                    "ip": pay["ip"],
                    "device_id": pay["device_id"],
                    "shipping_address": order["shipping"]["address"],
                    "account_id": self.customers[email]["account_id"],
                    "disputed": pay["charge_id"] in disputed_charges,
                    "refunded": pay["charge_id"] in self.refunds,
                }
            )
        return rows


def build_world(now: datetime | None = None) -> World:
    now = (now or datetime.now(UTC)).replace(microsecond=0)
    w = World(now=now)

    def customer(email: str, name: str, account_id: str, address: str) -> None:
        w.customers[email] = {
            "email": email,
            "name": name,
            "account_id": account_id,
            "address": address,
            "since": iso(w.ago(400)),
        }

    def order(
        oid: str,
        email: str,
        items: list[tuple[str, str, float]],
        placed: datetime,
        *,
        charge_id: str,
        last4: str,
        ip: str,
        device_id: str,
        avs: str = "Y (street + zip match)",
        cvv: str = "M (match)",
        address: str | None = None,
        carrier: str = "ShipCo",
        tracking: str = "",
        shipped: datetime | None = None,
        delivered: datetime | None = None,
        signature: str | None = None,
    ) -> dict[str, Any]:
        cust = w.customers[email]
        total = round(sum(price for _, _, price in items), 2)
        record = {
            "id": oid,
            "customer_email": email,
            "customer_name": cust["name"],
            "placed_at": iso(placed),
            "items": [{"sku": sku, "name": name, "qty": 1, "price": price} for sku, name, price in items],
            "total": total,
            "currency": "USD",
            "payment": {
                "charge_id": charge_id,
                "card_brand": "Visa",
                "last4": last4,
                "avs": avs,
                "cvv": cvv,
                "three_ds": "not attempted",
                "ip": ip,
                "device_id": device_id,
                "billing_address": cust["address"],
            },
            "shipping": {
                "address": address or cust["address"],
                "carrier": carrier,
                "tracking": tracking,
                "shipped_at": iso(shipped) if shipped else None,
                "delivered_at": iso(delivered) if delivered else None,
                "signature": signature,
            },
            "checkout": {
                "terms_accepted": True,
                "terms_accepted_at": iso(placed - timedelta(seconds=40)),
                "refund_policy_shown": True,
            },
        }
        w.orders[oid] = record
        return record

    def dispute(
        did: str,
        oid: str,
        reason: str,
        claim: str,
        opened_days_ago: float,
        respond_in_days: float,
        amount: float | None = None,
        charge_id: str | None = None,
    ) -> None:
        o = w.orders[oid]
        w.disputes[did] = {
            "id": did,
            "order_id": oid,
            "charge_id": charge_id or o["payment"]["charge_id"],
            "amount": amount if amount is not None else o["total"],
            "currency": "USD",
            "network": "Visa",
            "reason": reason,
            "network_code": REASONS[reason]["network_code"],
            "reason_label": REASONS[reason]["label"],
            "customer_name": o["customer_name"],
            "customer_email": o["customer_email"],
            "item": ", ".join(i["name"] for i in o["items"]),
            "cardholder_claim": claim,
            "opened_at": iso(w.ago(opened_days_ago)),
            "respond_by": iso(w.ahead(respond_in_days)),
            "status": "needs_response",
        }

    # -- DSP-1042: "never arrived" -- but ShipCo photographed it on the porch and the
    #    customer emailed two days later asking for another colour.
    customer("jamie.rivera@example.com", "Jamie Rivera", "acct_7731", "42 Maple Lane, Portland, OR 97214")
    o = order(
        "HS-20931", "jamie.rivera@example.com", [("PRK-CLD-M", "Cloud Down Parka (M, Oat)", 389.00)],
        w.ago(21, 19, 4), charge_id="ch_3Pa20931", last4="4242", ip="71.237.14.88",
        device_id="dv_2be81c", tracking="SC-77341920", shipped=w.ago(19, 9, 30),
        delivered=w.ago(16, 14, 12),
    )
    w.shipments[o["shipping"]["tracking"]] = {
        "tracking": o["shipping"]["tracking"],
        "order_id": o["id"],
        "carrier": "ShipCo",
        "service": "Ground, no signature required",
        "events": [
            {"at": iso(w.ago(19, 9, 30)), "where": "ShipCo Warehouse, Reno NV", "status": "Picked up"},
            {"at": iso(w.ago(18, 2, 15)), "where": "ShipCo Hub, Sacramento CA", "status": "In transit"},
            {"at": iso(w.ago(16, 7, 40)), "where": "ShipCo Depot, Portland OR", "status": "Out for delivery"},
            {"at": iso(w.ago(16, 14, 12)), "where": "42 Maple Lane, Portland OR", "status": "Delivered - front porch"},
        ],
        "delivered_at": iso(w.ago(16, 14, 12)),
        "delivery_gps": {"lat": 45.52311, "lng": -122.64874},
        "address_gps": {"lat": 45.52318, "lng": -122.64869},
        "gps_distance_m": 9,
        "photo": "delivery_photo_1042",
        "driver_note": "Left at front door, under covered porch.",
    }
    w.support["HS-20931"] = [
        {
            "at": iso(w.ago(14, 18, 2)),
            "from": "jamie.rivera@example.com",
            "subject": "Parka question!",
            "body": "Hi! The Cloud parka is amazing, so warm. Do you have it in moss green too? "
            "Would love one for my sister. - Jamie",
        },
        {
            "at": iso(w.ago(14, 20, 31)),
            "from": "support@hotspringsupply.example",
            "subject": "Re: Parka question!",
            "body": "So glad you love it, Jamie! Moss green restocks in October. We'll email you.",
        },
    ]
    dispute(
        "DSP-1042", "HS-20931", "product_not_received",
        "Cardholder states the parka was never delivered.", opened_days_ago=6, respond_in_days=4.2,
    )

    # -- DSP-1043: "unauthorized" -- but the same device, IP and address bought twice
    #    before without dispute (Visa Compelling Evidence 3.0).
    customer("alex.chen@example.com", "Alex Chen", "acct_5520", "88 Birch Ave, Austin, TX 78704")
    order(
        "HS-17312", "alex.chen@example.com", [("POV-KIT", "Pour-Over Starter Kit", 86.00)],
        w.ago(205, 8, 41), charge_id="ch_3Pa17312", last4="1881", ip="73.158.22.41",
        device_id="dv_9f3ca71", tracking="SC-61002217", shipped=w.ago(204), delivered=w.ago(201, 12, 5),
    )
    order(
        "HS-18855", "alex.chen@example.com", [("GRD-BURR", "Copper Burr Grinder", 142.00)],
        w.ago(297, 21, 17), charge_id="ch_3Pa18855", last4="1881", ip="73.158.22.19",
        device_id="dv_9f3ca71", tracking="SC-58830042", shipped=w.ago(296), delivered=w.ago(293, 15, 40),
    )
    o = order(
        "HS-21007", "alex.chen@example.com", [("ESP-SUMMIT", "Summit Espresso Machine", 1240.00)],
        w.ago(25, 7, 55), charge_id="ch_3Pa21007", last4="1881", ip="73.158.22.41",
        device_id="dv_9f3ca71", tracking="SC-77980135", shipped=w.ago(24, 10), delivered=w.ago(21, 11, 26),
        signature="A. Chen",
    )
    w.shipments[o["shipping"]["tracking"]] = {
        "tracking": o["shipping"]["tracking"],
        "order_id": o["id"],
        "carrier": "ShipCo",
        "service": "Ground, adult signature required",
        "events": [
            {"at": iso(w.ago(24, 10)), "where": "ShipCo Warehouse, Reno NV", "status": "Picked up"},
            {"at": iso(w.ago(21, 11, 26)), "where": "88 Birch Ave, Austin TX", "status": "Delivered - signed by A. Chen"},
        ],
        "delivered_at": iso(w.ago(21, 11, 26)),
        "delivery_gps": {"lat": 30.24951, "lng": -97.76612},
        "address_gps": {"lat": 30.24949, "lng": -97.76605},
        "gps_distance_m": 7,
        "photo": None,
        "driver_note": "Signed at door.",
    }
    dispute(
        "DSP-1043", "HS-21007", "fraudulent",
        "Cardholder does not recognise this transaction.", opened_days_ago=5, respond_in_days=6.5,
    )

    # -- DSP-1044: cancelled subscription that still renewed. Our billing sync bug, so
    #    the honest move is to accept and refund.
    customer("sam.patel@example.com", "Sam Patel", "acct_6102", "15 Cedar Ct, Denver, CO 80205")
    order(
        "HS-21110", "sam.patel@example.com", [("CLUB-MO", "Trail Club Monthly Box", 29.00)],
        w.ago(31, 0, 5), charge_id="ch_3Pa21110", last4="0077", ip="98.43.120.7",
        device_id="dv_44de10",
    )
    w.subscriptions["sam.patel@example.com"] = {
        "plan": "Trail Club Monthly Box",
        "price": 29.00,
        "events": [
            {"at": iso(w.ago(210)), "event": "subscribed"},
            {"at": iso(w.ago(34, 16, 48)), "event": "cancel_requested", "via": "account page"},
            {"at": iso(w.ago(34, 16, 48)), "event": "cancel_confirmation_email_sent"},
            {
                "at": iso(w.ago(31, 0, 5)),
                "event": "renewal_charged",
                "charge_id": "ch_3Pa21110",
                "note": "billing provider never received the cancellation (sync job failed)",
            },
        ],
    }
    dispute(
        "DSP-1044", "HS-21110", "subscription_canceled",
        "Cardholder cancelled the subscription before this renewal.", opened_days_ago=4, respond_in_days=8,
    )

    # -- DSP-1045: "not waterproof" -- the product page promised ISO 811 10,000 mm and
    #    the lab report proving it sits in the merchant's files.
    customer("morgan.lee@example.com", "Morgan Lee", "acct_8833", "301 Fern St, Seattle, WA 98103")
    o = order(
        "HS-20877", "morgan.lee@example.com", [("SHELL-STORM-L", "StormShell Rain Jacket (L, Teal)", 149.00)],
        w.ago(33, 12, 20), charge_id="ch_3Pa20877", last4="5005", ip="24.16.87.3",
        device_id="dv_ab0c42", tracking="SC-77210448", shipped=w.ago(32), delivered=w.ago(29, 16, 2),
    )
    w.shipments[o["shipping"]["tracking"]] = {
        "tracking": o["shipping"]["tracking"],
        "order_id": o["id"],
        "carrier": "ShipCo",
        "service": "Ground",
        "events": [{"at": iso(w.ago(29, 16, 2)), "where": "301 Fern St, Seattle WA", "status": "Delivered"}],
        "delivered_at": iso(w.ago(29, 16, 2)),
        "gps_distance_m": 12,
        "photo": None,
        "driver_note": "Left in mailroom.",
    }
    w.orders["HS-20877"]["product_page"] = {
        "url": "https://hotspringsupply.example/products/stormshell",
        "captured_at": iso(w.ago(33, 12, 18)),
        "claims": [
            "Waterproof rating: 10,000 mm hydrostatic head (ISO 811)",
            "Taped seams, 2.5-layer shell",
            "Care: wash cold, tumble dry low to reactivate the DWR coating",
        ],
        "image": "product_page_1045",
    }
    w.support["HS-20877"] = []  # the customer never contacted us or asked for a return
    w.merchant_files["stormshell_lab_report"] = {
        "title": "ISO 811 hydrostatic head test, StormShell batch SS-24",
        "lab": "Cascade Textile Labs",
        "result": "10,400 mm (pass, rated 10,000 mm)",
        "image": "lab_report_1045",
    }
    dispute(
        "DSP-1045", "HS-20877", "product_unacceptable",
        "Cardholder says the jacket was advertised as waterproof but leaked in the rain.",
        opened_days_ago=3, respond_in_days=9,
    )

    # -- DSP-1046: "charged twice" -- a double-click did create two charges, but the
    #    duplicate was refunded before the cardholder disputed it.
    customer("riley.kim@example.com", "Riley Kim", "acct_9014", "7 Willow Way, Boston, MA 02118")
    order(
        "HS-21142", "riley.kim@example.com", [("PLUSH-CAPY-2", "Capybara Plush, 2-pack", 64.00)],
        w.ago(18, 20, 11), charge_id="ch_3Pa21142", last4="3131", ip="66.31.204.90",
        device_id="dv_77f2e0", tracking="SC-77555012", shipped=w.ago(17), delivered=w.ago(15, 13, 30),
    )
    w.orders["HS-21142"]["payment"]["duplicate_charge"] = {
        "charge_id": "ch_3Pa21142b",
        "created_at": iso(w.ago(18, 20, 11) + timedelta(seconds=41)),
        "amount": 64.00,
        "cause": "double-submitted checkout button",
    }
    w.refunds["ch_3Pa21142b"] = {
        "refund_id": "re_3Pa21142b",
        "charge_id": "ch_3Pa21142b",
        "amount": 64.00,
        "created_at": iso(w.ago(17, 9, 3)),
        "status": "succeeded",
        "arn": "74521236012345678901234",  # acquirer reference number the cardholder's bank can trace
    }
    dispute(
        "DSP-1046", "HS-21142", "duplicate",
        "Cardholder was charged twice for the same order.", opened_days_ago=2, respond_in_days=11,
        charge_id="ch_3Pa21142b",
    )

    return w
