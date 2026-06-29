GUIDE_VERSION = 1

ROUTE_GUIDES = {
    "dashboard": "dashboard",
    "daily_operations": "daily-sales-list",
    "daily_operation_create": "daily-sale-create",
    "daily_operation_detail": "daily-operation",
    "fuel_deliveries": "fuel-refills-list",
    "fuel_delivery_create": "fuel-refill-create",
    "expenses": "expenses-list",
    "expense_create": "expense-create",
    "reports": "reports",
    "station_setup": "station-setup",
    "station_settings": "station-settings",
    "inventory": "inventory",
    "inventory_adjustment_create": "inventory-adjustment",
}

VALID_GUIDE_KEYS = frozenset(ROUTE_GUIDES.values())
