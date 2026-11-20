from smart_csv_mapper.ingest.profile import ColumnProfile


def column(name: str, *samples: str) -> ColumnProfile:
    return ColumnProfile(
        name=name, samples=list(samples), distinct_count=len(samples), empty_ratio=0.0
    )


SPANISH_COLUMNS = [
    column("Referencia", "C-001", "C-002"),
    column("Nombre", "María", "José"),
    column("Apellidos", "López García", "de la Fuente"),
    column("Correo", "maria@example.com"),
    column("Tlf", "612 345 678"),
    column("Importe (€)", "1.250,50", "80,00"),
    column("Vencimiento", "20/11/2026", "01/12/2026"),
]


def good_answer() -> dict[str, object]:
    return {
        "mappings": [
            {
                "target": "external_id",
                "source": "Referencia",
                "transform": "trim",
                "params": {},
                "confidence": 0.9,
            },
            {
                "target": "first_name",
                "source": "Nombre",
                "transform": "trim",
                "params": {},
                "confidence": 0.95,
            },
            {
                "target": "last_name",
                "source": "Apellidos",
                "transform": "trim",
                "params": {},
                "confidence": 0.95,
            },
            {
                "target": "email",
                "source": "correo",
                "transform": "lowercase_trim",
                "params": {},
                "confidence": 0.98,
            },
            {
                "target": "phone",
                "source": "Tlf",
                "transform": "normalize_phone",
                "params": {},
                "confidence": 0.9,
            },
            {
                "target": "amount_due",
                "source": "Importe (€)",
                "transform": "parse_eu_number",
                "params": {},
                "confidence": 0.9,
            },
            {
                "target": "due_date",
                "source": "Vencimiento",
                "transform": "parse_date",
                "params": {"format": "%d/%m/%Y"},
                "confidence": 0.85,
            },
        ]
    }
