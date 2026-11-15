# Synthetic, fictional portfolio-demo project data, not company or Procore records.

projects = [
    {
        "id": 101,
        "name": "Naples Medical Center",
        "status": "active",
        "rfis": [
            {
                "id": 1,
                "title": "Electrical routing conflict",
                "days_open": 12,
                "is_blocking": True
            },
            {
                "id": 2,
                "title": "Door hardware clarification",
                "days_open": 3,
                "is_blocking": False
            },
            {
                "id": 3,
                "title": "Mechanical duct conflict",
                "days_open": 8,
                "is_blocking": True
            }
        ]
    },
    {
        "id": 202,
        "name": "Gulfshore Residential Tower",
        "status": "active",
        "rfis": [
            {"id": 1, "title": "Transfer slab reinforcement conflicts with riser sleeves", "days_open": 15, "is_blocking": True},
            {"id": 2, "title": "Delayed approval of curtain-wall anchor redesign", "days_open": 10, "is_blocking": True},
            {"id": 3, "title": "Balcony waterproofing termination at facade sill", "days_open": 7, "is_blocking": True},
            {"id": 4, "title": "Apartment entry soffit dimension clarification", "days_open": 12, "is_blocking": False},
            {"id": 5, "title": "Facade panel joint alignment at amenity terrace", "days_open": 4, "is_blocking": False},
            {"id": 6, "title": "Architectural finish approval for elevator lobby reveals", "days_open": 2, "is_blocking": False}
        ]
    },
    {
        "id": 303,
        "name": "Southwest Logistics Center",
        "status": "active",
        "rfis": [
            {"id": 1, "title": "Underground fire main conflicts with stormwater crossing", "days_open": 11, "is_blocking": True},
            {"id": 2, "title": "Sprinkler branch clearance above warehouse conveyor", "days_open": 5, "is_blocking": True},
            {"id": 3, "title": "Dock leveler power disconnect location clarification", "days_open": 9, "is_blocking": False},
            {"id": 4, "title": "Warehouse rack impact on high-bay lighting layout", "days_open": 3, "is_blocking": False},
            {"id": 5, "title": "Site utility trench sequencing at truck court entrance", "days_open": 1, "is_blocking": False}
        ]
    }
]


# functions

def get_project_by_id(project_id: int):
    for project in projects:
        if project["id"] == project_id:
            return project

    return None

def is_critical_rfi(rfi: dict) -> bool:
    return rfi["is_blocking"] and rfi["days_open"] > 7


def get_critical_rfis(rfis: list) -> list:
    critical_rfis = []

    for rfi in rfis:
        if is_critical_rfi(rfi):
            critical_rfis.append(rfi)

    return critical_rfis


def get_blocking_rfis(rfis: list) -> list:
    blocking_rfis = []

    for rfi in rfis:
        if rfi["is_blocking"]:
            blocking_rfis.append(rfi)

    return blocking_rfis


def get_project_summary(project: dict) -> dict:
    summary = {
        "project_name": project["name"],
        "total_rfis": len(project["rfis"]),
        "critical_rfis": len(get_critical_rfis(project["rfis"])),
        "blocking_rfis": len(get_blocking_rfis(project["rfis"]))
    }

    return summary

def get_project_rfis(project: dict) -> list:
    return project["rfis"]
